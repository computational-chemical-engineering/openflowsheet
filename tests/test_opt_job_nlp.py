"""OPT WO-6 gates G12, G14 and G16 (design §4.10, §6; §9.5's OPT-A3 extension of G16), the
audited half: the `optimize` job with Ipopt.

- **G12** (job ≡ library): OPT-A2's record written by the `optimize` job — on the inline executor
  and in a spawned worker — equals `optimize_revision`'s byte for byte, on the same stored
  revision under the same policies. Masked (D-63), wall-clock members only: each start's
  `wall_time_s` in the report, each bundle's `started_at`/`elapsed_seconds` (and the
  `manifest_sha256` over them) in its `run-manifest.json`, and those files' SHA-256 in the record's
  manifest.
- **G14** (cancellation, budget): a cancellation made inside start 1's Ipopt iteration (OPT-A2,
  3 starts) ends the job `cancelled` at that iteration, with no report and no manifest output and
  start 0's bundles present as artifacts; a wall-time deadline that passes inside an Ipopt
  iteration (the executor's clock moved forward there) ends it `timed_out` at that iteration.
- **G16** (candidate = simulation): the report's change-set committed, a `solve` job of the new
  revision gives a certificate whose R0 content (`run.identity.r0_projection`'s `certificate`)
  equals the V1 certificate's: OPT-A2 `VERIFIED`; OPT-A3 `UNVERIFIED` with `rank_limitation`.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

from openflowsheet.application.jobs.model import TERMINAL_STATUSES
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.store import JOBS_DIR
from openflowsheet.application.types import Budgets, Change, Edit, JobRequest
from openflowsheet.run.identity import r0_projection
from openflowsheet.studies.nlp.revision import optimize_revision
from openflowsheet.verify.certificate import CheckPolicy

pytestmark = pytest.mark.nlp

OPT = Path(__file__).resolve().parents[1] / "benchmarks" / "opt"
EXPECTED = json.loads((OPT / "expected.json").read_bytes())
_POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert _POLICY is not None
POLICY = _POLICY
REPORT = "optimization-report.json"
MANIFEST = "optimization-manifest.json"
PATIENCE_S = 1800.0


def _document(case: str) -> dict[str, Any]:
    flowsheet = EXPECTED["flowsheets"][case]
    document: dict[str, Any] = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    return document


def _request(case: str) -> dict[str, Any]:
    request: dict[str, Any] = json.loads((OPT / "requests" / f"{case}.json").read_bytes())
    return request


def _seed(app: LocalApplication, case: str) -> str:
    edits = tuple(Edit("set", (key,), value) for key, value in _document(case).items())
    revision_id = app.commit_change(Change(edits=edits), None, f"seed-{case}").revision_id
    assert revision_id is not None
    return revision_id


def _stored(app: LocalApplication, revision_id: str) -> dict[str, Any]:
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, revision_id)
    assert revision is not None
    document: dict[str, Any] = revision.as_document()
    return document


def _optimize(revision_id: str, case: str, key: str, budgets: Budgets | None = None) -> JobRequest:
    request = JobRequest.from_document(
        {
            "operation": "optimize",
            "idempotency_key": key,
            "body": {"revision_id": revision_id, "request": _request(case)},
        }
    )
    return request if budgets is None else replace(request, budgets=budgets)


def _ended(app: LocalApplication, job_id: str) -> Any:
    deadline = time.monotonic() + PATIENCE_S
    while True:
        job = app.get_job(job_id)
        if job.status in TERMINAL_STATUSES:
            return job
        assert time.monotonic() < deadline, f"job {job_id} did not end"
        time.sleep(0.5)


def _record(app: LocalApplication, job_id: str) -> Path:
    return app.files_root / JOBS_DIR / job_id / "optimization"


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


#: The wall-clock members of a run bundle's manifest (D-63): when it started, how long it took, and
#: the manifest's own digest over them.
RUN_CLOCK = ("started_at", "elapsed_seconds", "manifest_sha256")


def _masked(files: dict[str, bytes]) -> dict[str, Any]:
    """G12's mask (D-63), wall-clock members only: each start's `wall_time_s` in the report, each
    bundle's `RUN_CLOCK` in its `run-manifest.json`, and those files' SHA-256 in the record's
    manifest. Every other byte is compared as it is."""
    masked: dict[str, Any] = dict(files)
    report = json.loads(files[REPORT])
    for start in report["starts"]:
        start["wall_time_s"] = None
    masked[REPORT] = report
    clocked = [REPORT]
    for name in files:
        if name.endswith("/run-manifest.json"):
            run = json.loads(files[name])
            for member in RUN_CLOCK:
                run[member] = None
            masked[name] = run
            clocked.append(name)
    manifest = json.loads(files[MANIFEST])
    for name in clocked:
        manifest["members"][name] = None
    masked[MANIFEST] = manifest
    return masked


# -- G12 -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def opt_a2(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, str, Path]]:
    """A project holding OPT-A2's revision, and the library's record of it."""
    directory = tmp_path_factory.mktemp("opt-job")
    project = directory / "project"
    with LocalApplication.create(project, project_id="opt-g12") as app:
        revision_id = _seed(app, "OPT-A2")
        document = _stored(app, revision_id)
    outcome = optimize_revision(
        document,
        _request("OPT-A2"),
        directory=directory / "library",
        solve_policy=POLICY,
        check_policy=CheckPolicy(),
    )
    assert outcome.record_dir is not None
    assert outcome.report.status == "KKT_POINT_VERIFIED"
    yield project, revision_id, outcome.record_dir


@pytest.mark.parametrize("executor", ["inline", "process"])
def test_g12_the_job_record_is_the_library_record(
    opt_a2: tuple[Path, str, Path], executor: str
) -> None:
    project, revision_id, library = opt_a2
    with LocalApplication.open(project, executor=executor) as app:  # type: ignore[arg-type]
        submitted = app.submit_job(_optimize(revision_id, "OPT-A2", f"g12-{executor}"))
        job = _ended(app, submitted.job.job_id)
        assert (job.status, job.error) == ("completed", None), job
        result = app.get_job_result(job.job_id)
        assert result.optimization is not None
        assert result.optimization["status"] == "KKT_POINT_VERIFIED"
        # A worker's log is its job's last output (T07 §9.2); the record's are the report, then
        # the manifest.
        outputs = [ref.artifact_id for ref in job.outputs]
        if executor == "process":
            assert outputs[-1] == f"{job.job_id}:worker.log"
            outputs = outputs[:-1]
        prefix = f"{job.job_id}:optimization/"
        assert outputs == [prefix + REPORT, prefix + MANIFEST]
        record = _record(app, job.job_id)
    found, expected = _files(record), _files(library)
    assert sorted(found) == sorted(expected)
    assert _masked(found) == _masked(expected)


# -- G14 -------------------------------------------------------------------------------------------


def _in_ipopt() -> bool:
    """Whether the caller runs inside Ipopt's intermediate callback (`greybox._Iterations`)."""
    frame: FrameType | None = sys._getframe(1)
    while frame is not None:
        code = frame.f_code
        if code.co_name == "__call__" and code.co_filename.endswith("greybox.py"):
            return True
        frame = frame.f_back
    return False


def test_g14_a_cancellation_inside_start_1_ends_the_job_cancelled(
    opt_a2: tuple[Path, str, Path],
) -> None:
    project, revision_id, _ = opt_a2
    with LocalApplication.open(project) as app:
        state: dict[str, Any] = {"fired": False, "after": 0}

        def cancel_in_start_1(job_id: str, check: int) -> None:
            if not _in_ipopt():
                return
            if state["fired"]:
                state["after"] += 1
                return
            done = _record(app, job_id) / "starts" / "0" / "resolve" / "run-manifest.json"
            if done.is_file():  # start 0's V1 is done: this Ipopt is start 1's
                state["fired"] = True
                app.cancel_job(job_id)

        app.executor.test_hook_on_check = cancel_in_start_1  # type: ignore[union-attr]
        try:
            submitted = app.submit_job(_optimize(revision_id, "OPT-A2", "g14-cancel"))
        finally:
            app.executor.test_hook_on_check = None  # type: ignore[union-attr]
        job = _ended(app, submitted.job.job_id)
        assert state["fired"]
        assert (job.status, job.ending.reason) == ("cancelled", "cancel_requested"), job
        assert state["after"] == 0  # Ipopt stopped at the iteration that saw the cancellation
        assert list(job.outputs) == []
        assert app.get_job_result(job.job_id).optimization is None
        record = _record(app, job.job_id)
        assert not (record / REPORT).exists() and not (record / MANIFEST).exists()
        assert not (record / "starts" / "1" / "resolve").exists()
        prefix = f"{job.job_id}:optimization/starts/0/"
        for name in ("start", "resolve"):
            row = app.store.artifact(prefix + name)
            assert row is not None and row.kind == "replay_bundle", name


def test_g14_a_deadline_inside_ipopt_ends_the_job_timed_out(
    opt_a2: tuple[Path, str, Path],
) -> None:
    project, revision_id, _ = opt_a2
    with LocalApplication.open(project) as app:
        executor = app.executor
        state: dict[str, Any] = {"fired": False, "after": 0}

        def expire_in_ipopt(job_id: str, check: int) -> None:
            if not _in_ipopt():
                return
            if state["fired"]:
                state["after"] += 1
            state["fired"] = True  # from here the clock is past any deadline

        executor.clock = lambda: time.monotonic() + (1e6 if state["fired"] else 0.0)  # type: ignore[union-attr]
        executor.test_hook_on_check = expire_in_ipopt  # type: ignore[union-attr]
        try:
            submitted = app.submit_job(
                _optimize(revision_id, "OPT-A2", "g14-budget", Budgets(wall_time_s=600.0))
            )
        finally:
            executor.test_hook_on_check = None  # type: ignore[union-attr]
            executor.clock = time.monotonic  # type: ignore[union-attr]
        job = _ended(app, submitted.job.job_id)
        assert state["fired"]
        assert (job.status, job.ending.reason) == ("timed_out", "wall_time_exhausted"), job
        assert state["after"] == 0
        assert list(job.outputs) == []
        record = _record(app, job.job_id)
        assert not (record / REPORT).exists() and not (record / MANIFEST).exists()


# -- G16 -------------------------------------------------------------------------------------------


def _certificate_r0(bundle: Path) -> dict[str, Any]:
    artifacts = {
        path.name: json.loads(path.read_bytes()) for path in (bundle / "artifacts").glob("*.json")
    }
    projection: dict[str, Any] = r0_projection(artifacts)["certificate"]
    return projection


@pytest.mark.parametrize(("case", "status"), [("OPT-A2", "VERIFIED"), ("OPT-A3", "UNVERIFIED")])
def test_g16_the_committed_candidate_solves_to_the_v1_certificate(
    case: str, status: str, tmp_path: Path
) -> None:
    with LocalApplication.create(tmp_path / "project", project_id="opt-g16") as app:
        revision_id = _seed(app, case)
        submitted = app.submit_job(_optimize(revision_id, case, f"g16-{case}"))
        job = _ended(app, submitted.job.job_id)
        assert job.status == "completed", job
        report = app.get_job_result(job.job_id).optimization
        assert report is not None and report["status"] == "KKT_POINT_VERIFIED", report
        candidate = report["candidate"]
        change, expected_revision, key = Change.from_change_set(candidate["change_set"])
        assert expected_revision == revision_id
        committed = app.commit_change(change, expected_revision, key).revision_id
        assert committed is not None
        solved = app.submit_job(
            JobRequest.from_document(
                {
                    "operation": "solve",
                    "idempotency_key": f"g16-solve-{case}",
                    "body": {"revision_id": committed},
                }
            )
        )
        solve = _ended(app, solved.job.job_id)
        assert solve.status == "completed", solve
        bundle = app.store.artifact(f"{solve.job_id}:bundle")
        assert bundle is not None
        found = _certificate_r0(app.files_root / bundle.relpath)
        v1 = _certificate_r0(_record(app, job.job_id) / candidate["resolve_record"])
    assert found == v1
    assert found["verification_status"] == status
    if status == "UNVERIFIED":
        assert "rank_limitation" in found["limitation_kinds"], found
