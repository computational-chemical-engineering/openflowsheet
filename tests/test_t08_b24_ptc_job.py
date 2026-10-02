"""T08.B24, V14 (b3) (T08 build-first spec §A4.7): `T08-ptc-v1` is selectable through the
application on the PTC-R1 flowsheet.

On the §A2 revision (`benchmarks/t08/ptc_r1/revision.json`) committed to a fresh project, a
`solve` job submitted through `LocalApplication.submit_job` with policy `T08-ptc-v1` ends typed
and its PTC core runs (`branch_provenance[0].core == "ptc"`); the policy is one that
`get_project` lists under `solve_policies`. The outcome is recorded and not asserted (§A4.7).
Measured at T08 close on `ref-x86-64` (src equal to `C` = `67c66d9`): `CONVERGED`, `VERIFIED`,
from the traversal start, 21 PTC iterations.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_jobs_support import commit

from openflowsheet.application.jobs.model import TERMINAL_STATUSES
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import JobRequest, SolveBody

REVISION = REPO_ROOT / "benchmarks" / "t08" / "ptc_r1" / "revision.json"
POLICY = "T08-ptc-v1"


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    document = json.loads(REVISION.read_text(encoding="utf-8"))
    document.pop("revision_id", None)
    with LocalApplication.create(
        tmp_path_factory.mktemp("t08b24") / "p", project_id="t08-b24"
    ) as app:
        revision_id = commit(app, document)
        project = dispatch(app, "get_project", {})
        job = app.submit_job(
            JobRequest("solve", "t08-b24", SolveBody(revision_id, policy_id=POLICY))
        ).job
        result = app.get_job_result(job.job_id).run_result
        artifacts = app.files_root / "jobs" / job.job_id / "bundle" / "artifacts"
        yield {
            "project": project,
            "job": job,
            "result": result,
            "artifacts": {path.name: path for path in artifacts.iterdir()},
        }


def test_b24_the_policy_is_offered_by_get_project(solved: dict[str, Any]) -> None:
    offered = [entry["policy_id"] for entry in solved["project"]["solve_policies"]]
    assert POLICY in offered


def test_b24_the_job_ends_typed(solved: dict[str, Any]) -> None:
    """A terminal status of the job model (ADR 0020), never left running; the run's outcome, when
    there is one, is recorded here and not asserted."""
    job, result = solved["job"], solved["result"]
    assert job.status in TERMINAL_STATUSES, (job.status, job.error)
    assert result is None or result.outcome, job.error


def test_b24_the_ptc_core_runs(solved: dict[str, Any]) -> None:
    artifacts: dict[str, Path] = solved["artifacts"]
    name = (
        "solution-certificate.json"
        if "solution-certificate.json" in artifacts
        else "failure-bundle.json"
    )
    recorded = json.loads(artifacts[name].read_text(encoding="utf-8"))
    assert recorded["branch_provenance"][0]["core"] == "ptc", name
