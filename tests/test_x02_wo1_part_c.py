"""X02 WO-1 (Part C; design note `docs/design/X02-warm-starts.md` §3.3, D9, §5.4; gate G1): under
`T08-warm-v1` a `revision_coupled` run records the k = 0 inner warm start of its coupling in the
bundle, whatever its number of outer iterations, and labels that inner solve
`compatible_warm_start`.

- J₀ is a cold (`default`) solve of the stand-in loop, J₁ a `T08-warm-v1` solve of the same
  revision: its lineage candidate is J₀, so the gate does not depend on how many outer iterations
  J₁ takes (the stand-in loop takes two, k = 0 and k = 1, so the k = 0 record is not the final
  inner run's).
- J₁'s `solve-path.json` carries `warm_start.status == "accepted"` naming J₀, and the record's
  `iterations[0].inner.start` is `compatible_warm_start`; the later inner solves keep
  `user_start`.
- Reproducing J₁ gives `MATCH`.
- Control: J₁'s bundle written again without the member reruns cold at k = 0 and is not `MATCH`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_jobs_support import commit

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import ReplayPolicy
from openflowsheet.run.bundle import read_artifact, read_manifest, write_bundle

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
WARM = "T08-warm-v1"


def _bundle(app: LocalApplication, job: dict[str, Any]) -> Path:
    (ref,) = [output for output in job["outputs"] if output["kind"] == "replay_bundle"]
    row = app.store.artifact(ref["artifact_id"])
    assert row is not None
    return app.files_root / row.relpath


def _solve(app: LocalApplication, key: str, revision_id: str, policy_id: str) -> dict[str, Any]:
    body = {"revision_id": revision_id, "policy_id": policy_id}
    request = {"operation": "solve", "idempotency_key": key, "body": body}
    job: dict[str, Any] = dispatch(app, "submit_job", request)["job"]
    assert (job["status"], job["error"]) == ("completed", None)
    return job


@dataclass(frozen=True)
class Loop:
    app: LocalApplication
    cold: dict[str, Any]
    warm: dict[str, Any]
    warm_bundle: Path


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Loop]:
    with LocalApplication.create(
        tmp_path_factory.mktemp("x02wo1") / "p", project_id="x02-wo1"
    ) as app:
        revision_id = commit(app, json.loads(LOOP_PATH.read_text(encoding="utf-8")))
        cold = _solve(app, "j0", revision_id, "default")
        warm = _solve(app, "j1", revision_id, WARM)
        yield Loop(app, cold, warm, _bundle(app, warm))


def test_g1_the_warm_run_needs_more_than_one_outer_iteration(solved: Loop) -> None:
    """The case the defect needs: the k = 0 inner run is not the final one."""
    record = read_artifact(solved.warm_bundle, "external-coupling.json")
    assert record["outcome"] == "CONVERGED"
    assert len(record["iterations"]) > 1


def test_g1_the_k0_warm_start_is_recorded_and_labelled(solved: Loop) -> None:
    member = read_artifact(solved.warm_bundle, "solve-path.json").get("warm_start")
    assert member is not None
    assert (member["status"], member["reason"], member["selection"]) == (
        "accepted",
        None,
        "store-latest-verified-lineage-v1",
    )
    assert member["source_job_id"] == solved.cold["job_id"]
    record = read_artifact(solved.warm_bundle, "external-coupling.json")
    starts = [item["inner"]["start"] for item in record["iterations"]]
    assert starts == ["compatible_warm_start"] + ["user_start"] * (len(starts) - 1)
    result = dispatch(solved.app, "get_job_result", {"job_id": solved.warm["job_id"]})
    assert result["run_result"]["verification_status"] == "VERIFIED"


def test_g1_the_cold_run_has_no_member_and_its_route_initializer_label(solved: Loop) -> None:
    cold = _bundle(solved.app, solved.cold)
    assert "warm_start" not in read_artifact(cold, "solve-path.json")
    record = read_artifact(cold, "external-coupling.json")
    assert record["iterations"][0]["inner"]["start"] == "route_initializer"


def test_g1_reproducing_the_warm_run_matches(solved: Loop) -> None:
    report = solved.app.reproduce(solved.warm_bundle, ReplayPolicy(rerun=True))
    assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
    assert report.verdict == "MATCH", report.differences


def test_g1_control_without_the_record_the_rerun_starts_cold_and_differs(
    solved: Loop, tmp_path: Path
) -> None:
    manifest, _ = read_manifest(solved.warm_bundle)
    artifacts = {name: read_artifact(solved.warm_bundle, name) for name in manifest.artifacts}
    del artifacts["solve-path.json"]["warm_start"]
    write_bundle(tmp_path / "stripped", manifest, artifacts)
    report = solved.app.reproduce(tmp_path / "stripped", ReplayPolicy(rerun=True))
    assert report.verdict != "MATCH"
    assert any("solve-path.json" in entry for entry in report.differences), report.differences
