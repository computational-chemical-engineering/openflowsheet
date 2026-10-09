"""M04.A16 and the `surrogate_study` job operation (spec §10.3; ADR 0037 D6, ADR 0019 Amendment 5).

Through the application, with the registered stand-in `standin-x025-v1` (the only registered
parent that runs in the default gate): admission (a registered parent, a plan registered for it),
the stages, the two outputs, the answer, the cache-first resubmission, the budget refusal, and
M04's surface move decomposing onto M02's (`tests/m04_schema_support.py`). The synthetic parents
are not reachable from a request (they are not registered), so A17–A24 run at the library level
(`tests/test_m04_study.py`).

A16's tolerances (spec §11): β_X within 10⁻¹⁴ of (0.25, 0, …), β_T within 10⁻¹² K of 0, q̂ ≤ 10⁻¹⁰.
Floor: the stand-in's map is X ≡ 0.25 exactly, ΔT ≡ 0, so the residuals are the QR solve's roundoff
(one ulp of 0.25 is 5.6 × 10⁻¹⁷; κ = 8 at the prefix's training set).
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from m04_schema_support import without_m04
from t07_jobs_support import lifecycle_violations, response_schema_violations

from openflowsheet.adapters import variants
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import JobResult, schema_errors
from openflowsheet.canonical import document_sha256
from openflowsheet.studies.surrogate.manifest import Q0, check_manifest

STANDIN = variants.registered_variant("standin-x025-v1")
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
#: Spec §18 A1.4: the manifest, then the evidence that names it.
STUDY_KINDS = ["surrogate_manifest", "model_evidence"]


def body(
    variant: variants.Variant = STANDIN,
    *,
    plan_id: str = "it1-prefix",
    budget: int = 1000,
    sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "parent": {
            "model_id": variant.model_id,
            "variant_id": variant.variant_id,
            "variant_sha256": sha256 or variant.sha256,
        },
        "plan_id": plan_id,
        "budget": {"max_cold_experiments": budget},
    }


def submit(app: LocalApplication, key: str, document: dict[str, Any]) -> dict[str, Any]:
    request = {"operation": "surrogate_study", "idempotency_key": key, "body": document}
    response: dict[str, Any] = dispatch(app, "submit_job", request)
    return response


def result_of(app: LocalApplication, job_id: str) -> dict[str, Any]:
    answer: dict[str, Any] = dispatch(app, "get_job_result", {"job_id": job_id})
    return answer


def read(app: LocalApplication, artifact_id: str) -> dict[str, Any]:
    row = app.store.artifact(artifact_id)
    assert row is not None
    document: dict[str, Any] = json.loads((app.files_root / row.relpath).read_bytes())
    return document


def attempts(app: LocalApplication) -> list[Path]:
    return sorted(app.files_root.glob("experiments/*/*/attempt-*.json"))


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


def test_a16_the_standin_prefix_study_through_the_job_operation(app: LocalApplication) -> None:
    job = submit(app, "standin", body())["job"]
    assert (job["status"], job["error"]) == ("completed", None)
    assert [output["kind"] for output in job["outputs"]] == STUDY_KINDS
    events = dispatch(app, "list_job_events", {"job_id": job["job_id"]})["items"]
    assert [e["progress"]["stage"] for e in events if e["kind"] == "progress"] == [
        "resolve",
        "study",
        "record",
    ]
    answer = result_of(app, job["job_id"])
    assert (answer["operation"], answer["run_result"], answer["replay_report"]) == (
        "surrogate_study",
        None,
        None,
    )
    study = answer["surrogate_study"]
    assert (
        schema_errors("surrogate-manifest.schema.json#/$defs/surrogate_study_result", study) == []
    )
    assert (study["cold_experiments"], study["cache_hits"], study["cache_misses"]) == (199, 0, 199)
    assert study["surrogate_id"] == "m04q7-standin-x025-v1-it1-prefix"
    manifest = read(app, job["outputs"][0]["artifact_id"])
    evidence = read(app, job["outputs"][1]["artifact_id"])
    assert study["manifest_sha256"] == document_sha256(manifest) == job["outputs"][0]["sha256"]
    assert study["evidence_sha256"] == document_sha256(evidence) == job["outputs"][1]["sha256"]
    assert check_manifest(manifest) == []
    # A16: no failures, the exact fit of a constant map, q̂ at roundoff.
    for split in ("training", "calibration", "test", "gradient"):
        assert manifest["splits"][split]["failed"] == []
        assert manifest["splits"][split]["incomplete"] == []
    beta_x = manifest["predictor"]["coefficients"]["X"]
    beta_t = manifest["predictor"]["coefficients"]["dT_K"]
    assert abs(beta_x[0] - 0.25) <= 1e-14
    assert max(abs(b) for b in beta_x[1:]) <= 1e-14
    assert max(abs(b) for b in beta_t) <= 1e-12
    assert manifest["calibration"]["q_hat"] <= 1e-10
    assert manifest["qualifications"][0] == Q0
    assert evidence["scope"]["evidence_class"] == "synthetic_verification"
    assert manifest["parent"]["variant_sha256"] == STANDIN.sha256
    # The experiment records are artifacts of the job, not its outputs (R-237's sink).
    with app.store.reading() as connection:
        kinds = dict(
            connection.execute(
                "SELECT kind, COUNT(*) FROM artifacts WHERE job_id = ? GROUP BY kind",
                (job["job_id"],),
            ).fetchall()
        )
    assert kinds == {
        "experiment_request": 199,
        "experiment_attempt": 199,
        "experiment_result": 199,
        "model_evidence": 1,
        "surrogate_manifest": 1,
    }
    assert JobResult.from_document(answer).as_document() == answer


def test_a38_the_evidence_names_the_manifest_written_by_the_same_job(
    app: LocalApplication,
) -> None:
    """M04.A38 (spec §18 A1.4): the outputs are [manifest, evidence]; the evidence's
    `subject.artifact_ref` is the SHA-256 of that manifest; the manifest has no
    `evidence_sha256`; the checker takes the manifest alone and accepts it."""
    job = submit(app, "a38", body())["job"]
    outputs = job["outputs"]
    assert [output["kind"] for output in outputs] == ["surrogate_manifest", "model_evidence"]
    manifest = read(app, outputs[0]["artifact_id"])
    evidence = read(app, outputs[1]["artifact_id"])
    assert "evidence_sha256" not in manifest
    assert evidence["subject"]["artifact_ref"] == outputs[0]["sha256"] == document_sha256(manifest)
    assert schema_errors("model-evidence.schema.json", evidence) == []
    # The checker reads no evidence: one parameter, the manifest, and nothing else is consulted.
    assert list(inspect.signature(check_manifest).parameters) == ["manifest"]
    assert check_manifest(manifest) == []
    # A null subject (the rejected alternative) is refused by the schema.
    unnamed = {**evidence, "subject": {**evidence["subject"], "artifact_ref": None}}
    assert any("artifact_ref" in e for e in schema_errors("model-evidence.schema.json", unnamed))


def test_a_resubmission_with_every_record_cached_reproduces_the_manifest(
    app: LocalApplication,
) -> None:
    first = submit(app, "first", body())["job"]
    before = attempts(app)
    second = submit(app, "second", body(budget=0))["job"]
    assert second["status"] == "completed"
    answer = result_of(app, second["job_id"])["surrogate_study"]
    assert (answer["cold_experiments"], answer["cache_hits"], answer["cache_misses"]) == (0, 199, 0)
    assert (
        answer["manifest_sha256"]
        == result_of(app, first["job_id"])["surrogate_study"]["manifest_sha256"]
    )
    assert attempts(app) == before


def test_a_budget_below_the_cache_misses_is_refused_with_nothing_written(
    app: LocalApplication,
) -> None:
    job = submit(app, "short", body(budget=198))["job"]
    assert (job["status"], job["outputs"]) == ("completed", [])
    answer = result_of(app, job["job_id"])["surrogate_study"]
    assert answer == {
        "verdict": "INSUFFICIENT_EVIDENCE",
        "insufficient": ["budget_below_plan"],
        "not_promotable": [],
        "surrogate_id": "m04q7-standin-x025-v1-it1-prefix",
        "manifest_sha256": None,
        "evidence_sha256": None,
        "cold_experiments": 0,
        "cache_hits": 0,
        "cache_misses": 199,
    }
    assert attempts(app) == []
    assert list(app.files_root.glob("experiments/*/*/*.json")) == []


@pytest.mark.parametrize(
    ("document", "pointer", "reason"),
    [
        # A03: the prefix plan is registered for synthetic parents only.
        (body(REAL), "/body/plan_id", "plan_not_registered_for_parent"),
        # Spec §5.5: at most three iterations; `it4` has no committed plan file.
        (body(plan_id="it4"), "/body/plan_id", "plan_not_registered"),
        # Spec §18 A1.2: `it2` with no `it1` manifest of the parent in the project.
        (body(plan_id="it2"), "/body/plan_id", "iteration_not_permitted"),
        (body(sha256="0" * 64), "/body/parent/variant_sha256", None),
    ],
)
def test_admission_refuses_an_unregistered_parent_or_plan(
    app: LocalApplication, document: dict[str, Any], pointer: str, reason: str | None
) -> None:
    with pytest.raises(ApplicationError) as raised:
        submit(app, "refused", document)
    error = raised.value.error
    assert error.code == "invalid_request"
    assert error.detail["pointer"] == pointer
    assert error.detail.get("reason") == reason
    assert dispatch(app, "list_jobs", {})["items"] == []
    assert attempts(app) == []


def test_m04s_responses_decompose_onto_m02s_snapshots() -> None:
    """With M04's additions removed, every operation's resolved response is its M02 snapshot."""
    import test_t07_w5e_application_results as r4

    before = {
        **r4.SNAPSHOT_AT_B13D556,
        **r4.SNAPSHOT_AMENDMENT_2,
        **r4.SNAPSHOT_AMENDMENT_3,
        **r4.SNAPSHOT_M02,
    }
    moved = []
    for name, operation in OPERATIONS.items():
        resolved = r4.resolved_response(operation)
        assert r4._digest(without_m04(resolved)) == before[name], name
        if r4._digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(r4.SNAPSHOT_M04)
