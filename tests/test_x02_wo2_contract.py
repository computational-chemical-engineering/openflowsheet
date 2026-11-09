"""X02 WO-2: the declared start's contract and the explicit inner start (ADR 0070, ADR 0019
Amendment 15; design note `docs/design/X02-warm-starts.md` §5.1–§5.3; gates G2 and G6's contract
half).

The states are T08 W4's (`tests/test_t08_w4_warm_starts.py`, §B5): the source is
`SYN-001-nominal` solved under `default`; the target is its child with the splitter's recycle
fraction 0.5 → 0.95, solved under `default` with `warm_start.job_id` naming a source job.

- **G2.** An explicit `job_id` is its own opt-in under `default`: the bundle's `warm_start` is
  `selection` `explicit-v1`, `accepted`, naming the source; the run converges and verifies, and
  replay gives `MATCH` with the record reproduced. A source that converged but did not verify
  (`FAILED`, tightened tolerances) is accepted as well: a start is only a start. A tampered
  source state is `rejected` for `integrity`, and the run's state and certificate are R0-equal
  to the cold run's. The cold `default` run writes no member.
- **A1, A2** (admission, `invalid_request`, no job created): an unknown job id, a `reproduce`
  job and a solve job without a solution state are each `warm_start_source_missing(<id>)` at
  `/body/warm_start/job_id`; a `coupling` key that is not an instance id is
  `warm_start_unit_unknown(<key>)` at `/body/warm_start/coupling/<key>`.
- **Identity.** A request without `warm_start` hashes as before (its document has no member);
  one with it differs.
- **The legacy route** (§5.2): a declared `job_id` on a `legacy_eo` solve is recorded `rejected`
  (`route`), and the solve's state is the one without it.
- **G6, transports.** Python, CLI, HTTP and MCP each accept one solve with `warm_start` and refuse
  A1 with the same `invalid_request`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit
from t07_transport_support import dispatched

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import (
    JobRequest,
    ReplayPolicy,
    SolveBody,
    WarmStartDeclaration,
)
from openflowsheet.run import solution_state
from openflowsheet.run.identity import r0_projection
from openflowsheet.verify.checks import KIND_TOLERANCE

EXPLICIT = "explicit-v1"


def _child(recycle: float) -> dict[str, Any]:
    """The source with only the recycle fraction changed, in both places it is declared (T08 W4's
    target, `tests/test_t08_w4_warm_starts.py`)."""
    document = CORPUS["SYN-001-nominal"]()
    document.pop("revision_id", None)
    (splitter,) = [item for item in document["instances"] if item["id"] == "splitter"]
    splitter["parameters"]["split_fraction"]["value"] = recycle
    (spec,) = [item for item in document["specifications"] if item["id"] == "SPEC-splitter-r"]
    spec["value"] = recycle
    return document


@dataclass(frozen=True)
class Solved:
    job_id: str
    outcome: str | None
    verdict: str | None
    directory: Path
    artifacts: dict[str, Any]

    @property
    def warm_start(self) -> dict[str, Any] | None:
        member: dict[str, Any] | None = self.artifacts["solve-path.json"].get("warm_start")
        return member

    def messages(self, kind: str) -> list[str]:
        events = self.artifacts["solve-events.json"]
        return [event["message"] for event in events if event["kind"] == kind]


def _read(directory: Path) -> dict[str, Any]:
    return {
        path.name: json.loads(path.read_bytes())
        for path in sorted((directory / "artifacts").iterdir())
    }


def _solve(app: LocalApplication, revision_id: str, **body: Any) -> Solved:
    key = f"x02-wo2-{len(app.list_jobs(limit=200).items)}"
    job = app.submit_job(JobRequest("solve", key, SolveBody(revision_id, **body))).job
    assert job.status == "completed", (job.status, job.error)
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    directory = app.files_root / "jobs" / job.job_id / "bundle"
    return Solved(
        job.job_id, result.outcome, result.verification_status, directory, _read(directory)
    )


def _from(job_id: str) -> WarmStartDeclaration:
    return WarmStartDeclaration(job_id=job_id)


@dataclass(frozen=True)
class Project:
    app: LocalApplication
    source_revision: str
    target_revision: str
    source: Solved
    failed_source: Solved
    explicit: Solved
    explicit_failed: Solved
    cold: Solved


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Project]:
    tightened = {kind: value * 1e-12 for kind, value in KIND_TOLERANCE.items()}
    with LocalApplication.create(
        tmp_path_factory.mktemp("x02wo2") / "p", project_id="x02-wo2"
    ) as app:
        source_revision = commit(app, CORPUS["SYN-001-nominal"]())
        source = _solve(app, source_revision)
        failed_source = _solve(app, source_revision, check_tolerances=tightened)
        target_revision = commit(app, _child(0.95))
        explicit = _solve(app, target_revision, warm_start=_from(source.job_id))
        explicit_failed = _solve(app, target_revision, warm_start=_from(failed_source.job_id))
        cold = _solve(app, target_revision)
        yield Project(
            app,
            source_revision,
            target_revision,
            source,
            failed_source,
            explicit,
            explicit_failed,
            cold,
        )


# -- G2: the explicit inner start -----------------------------------------------------------------


def test_g2_an_explicit_source_is_its_own_opt_in_under_default(project: Project) -> None:
    assert (project.source.outcome, project.source.verdict) == ("CONVERGED", "VERIFIED")
    run = project.explicit
    assert run.warm_start is not None
    assert {key: run.warm_start[key] for key in ("record", "selection", "status", "reason")} == {
        "record": "warm-start-v1",
        "selection": EXPLICIT,
        "status": "accepted",
        "reason": None,
    }
    assert (run.warm_start["source_job_id"], run.warm_start["source_revision_id"]) == (
        project.source.job_id,
        project.source_revision,
    )
    # The candidate is the source's stored solution state, as the record carries it.
    assert run.warm_start["candidate"] == project.source.artifacts[solution_state.NAME]
    assert run.messages("initializer_candidate") == ["compatible_warm_start(present)"]
    assert run.messages("initializer_rejected") == []
    certificate = run.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "compatible_warm_start"
    assert run.artifacts["solve-policy.json"]["policy_id"] == "T06-revision-v2"
    assert (run.outcome, run.verdict) == ("CONVERGED", "VERIFIED")


def test_g2_the_cold_default_run_writes_no_member(project: Project) -> None:
    assert project.cold.warm_start is None
    certificate = project.cold.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "traversal-G0-v1"
    assert (project.cold.outcome, project.cold.verdict) == ("CONVERGED", "VERIFIED")


def test_g2_a_source_that_did_not_verify_is_accepted(project: Project) -> None:
    assert project.failed_source.verdict == "FAILED"
    assert solution_state.NAME in project.failed_source.artifacts
    run = project.explicit_failed
    assert run.warm_start is not None
    assert (run.warm_start["selection"], run.warm_start["status"]) == (EXPLICIT, "accepted")
    assert run.warm_start["source_job_id"] == project.failed_source.job_id
    assert (run.outcome, run.verdict) == ("CONVERGED", "VERIFIED")


def test_g2_replay_reruns_from_the_record_and_matches(project: Project, tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "fresh", project_id="x02-wo2-replay") as app:
        report = app.reproduce(project.explicit.directory, ReplayPolicy(rerun=True))
        assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
        assert report.verdict == "MATCH", report.differences
        job_id = app.list_jobs(limit=10).items[-1].job_id
        rerun = _read(app.files_root / "jobs" / job_id / "rerun")
    assert rerun["solve-path.json"]["warm_start"] == project.explicit.warm_start
    assert r0_projection(rerun) == r0_projection(project.explicit.artifacts)


def test_g2_a_tampered_source_is_rejected_for_integrity(tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "p", project_id="x02-wo2-tampered") as app:
        source = _solve(app, commit(app, CORPUS["SYN-001-nominal"]()))
        path = source.directory / "artifacts" / solution_state.NAME
        document = json.loads(path.read_bytes())
        document["variables"]["S2.T"] = document["variables"]["S2.T"] + 1.0
        path.write_text(json.dumps(document), encoding="utf-8")
        target = commit(app, _child(0.95))
        run = _solve(app, target, warm_start=_from(source.job_id))
        cold = _solve(app, target)
    assert run.warm_start is not None
    assert (run.warm_start["selection"], run.warm_start["status"], run.warm_start["reason"]) == (
        EXPLICIT,
        "rejected",
        "integrity",
    )
    assert run.messages("initializer_rejected") == ["warm_start_rejected(integrity)"]
    assert run.artifacts[solution_state.NAME] == cold.artifacts[solution_state.NAME]
    certificate = run.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "traversal-G0-v1"
    # The state and the certificate are R0-equal to the cold run's; the trace differs by the
    # rejection's own `initializer_*` events, and the record by its member.
    warm_r0, cold_r0 = r0_projection(run.artifacts), r0_projection(cold.artifacts)
    for member in ("certificate", "solution_state", "solve_path", "execution_plan"):
        assert warm_r0[member] == cold_r0[member], member
    assert (run.outcome, run.verdict) == ("CONVERGED", "VERIFIED")


# -- A1, A2: admission ----------------------------------------------------------------------------


def _refused(app: LocalApplication, body: dict[str, Any], key: str) -> dict[str, Any]:
    before = len(app.list_jobs(limit=200).items)
    request = {"operation": "solve", "idempotency_key": key, "body": body}
    error, document = dispatched(app, "submit_job", request)
    assert error, document
    assert len(app.list_jobs(limit=200).items) == before  # no job created
    refusal: dict[str, Any] = document
    return refusal


def _a1(app: LocalApplication, revision_id: str, job_id: str, key: str) -> None:
    body = {"revision_id": revision_id, "warm_start": {"job_id": job_id}}
    refusal = _refused(app, body, key)
    assert (refusal["code"], refusal["message"]) == (
        "invalid_request",
        f"warm_start_source_missing({job_id})",
    )
    assert refusal["detail"]["pointer"] == "/body/warm_start/job_id"


def test_a1_an_unknown_job_is_refused(project: Project) -> None:
    _a1(project.app, project.target_revision, "job-999999", "a1-unknown")


def test_a1_a_reproduce_job_is_refused(project: Project) -> None:
    app = project.app
    (ref,) = [
        output
        for output in app.get_job(project.source.job_id).outputs
        if output.kind == "replay_bundle"
    ]
    body = {"bundle_artifact_id": ref.artifact_id, "rerun": False}
    request = {"operation": "reproduce", "idempotency_key": "a1-reproduce-job", "body": body}
    error, submitted = dispatched(app, "submit_job", request)
    assert not error, submitted
    _a1(app, project.target_revision, submitted["job"]["job_id"], "a1-reproduce")


def test_a1_a_solve_job_without_a_solution_state_is_refused(project: Project) -> None:
    starved = _solve(project.app, project.source_revision, max_property_calls=1)
    assert starved.outcome != "CONVERGED"
    assert solution_state.NAME not in starved.artifacts
    _a1(project.app, project.target_revision, starved.job_id, "a1-no-state")


def test_a2_an_unknown_coupling_unit_is_refused(project: Project) -> None:
    body = {
        "revision_id": project.target_revision,
        "warm_start": {"coupling": {"no_such_unit": {"X": 0.2, "dT_K": 80.0}}},
    }
    refusal = _refused(project.app, body, "a2-unknown")
    assert (refusal["code"], refusal["message"]) == (
        "invalid_request",
        "warm_start_unit_unknown(no_such_unit)",
    )
    assert refusal["detail"]["pointer"] == "/body/warm_start/coupling/no_such_unit"


def test_the_schema_refuses_an_empty_or_unknown_member(project: Project) -> None:
    for index, warm_start in enumerate(({}, {"job": "x"}, {"coupling": {}})):
        body = {"revision_id": project.target_revision, "warm_start": warm_start}
        refusal = _refused(project.app, body, f"schema-{index}")
        assert refusal["code"] == "invalid_request", refusal


# -- identity -------------------------------------------------------------------------------------


def test_a_request_without_warm_start_is_unchanged() -> None:
    plain = JobRequest("solve", "k", SolveBody("rev-000001"))
    assert "warm_start" not in plain.as_document()["body"]
    declared = JobRequest("solve", "k", SolveBody("rev-000001", warm_start=_from("job-000001")))
    assert declared.as_document()["body"]["warm_start"] == {"job_id": "job-000001"}
    assert declared.request_sha256 != plain.request_sha256
    assert JobRequest.from_document(declared.as_document()) == declared
    coupling = WarmStartDeclaration(coupling={"reactor": (0.2, 80.0)})
    document = coupling.as_document()
    assert document == {"coupling": {"reactor": {"X": 0.2, "dT_K": 80.0}}}
    assert WarmStartDeclaration._build(document) == coupling


# -- the legacy route (§5.2) ----------------------------------------------------------------------


def test_the_legacy_route_records_a_declared_source_rejected(
    project: Project, tmp_path: Path
) -> None:
    app = project.app
    legacy = commit(app, CORPUS["SYN-001-A02-360"]())
    run = _solve(app, legacy, warm_start=_from(project.source.job_id))
    cold = _solve(app, legacy)
    assert run.artifacts["solve-path.json"]["solve_path"] == "legacy_eo"
    assert run.warm_start is not None
    assert (run.warm_start["selection"], run.warm_start["status"], run.warm_start["reason"]) == (
        EXPLICIT,
        "rejected",
        "route",
    )
    assert run.warm_start["source_job_id"] == project.source.job_id
    assert cold.warm_start is None
    # The solve ran as without it.
    assert run.artifacts[solution_state.NAME] == cold.artifacts[solution_state.NAME]
    assert run.artifacts["solve-events.json"] == cold.artifacts["solve-events.json"]
    assert (run.outcome, run.verdict) == (cold.outcome, cold.verdict) == ("CONVERGED", "VERIFIED")
    with LocalApplication.create(tmp_path / "fresh", project_id="x02-wo2-legacy") as fresh:
        report = fresh.reproduce(run.directory, ReplayPolicy(rerun=True))
    assert report.verdict == "MATCH", report.differences


# -- G6: every transport accepts the member and refuses A1 ----------------------------------------


@dataclass(frozen=True)
class Shared:
    project: Path
    revision_id: str
    source_job_id: str
    grant: tuple[Any, str]


@pytest.fixture(scope="module")
def shared(tmp_path_factory: pytest.TempPathFactory) -> Shared:
    from openflowsheet.application.authz import grant

    project = tmp_path_factory.mktemp("x02wo2-transports") / "project"
    with LocalApplication.create(project, project_id="x02-wo2-transports") as app:
        source = _solve(app, commit(app, CORPUS["SYN-001-nominal"]()))
        revision_id = commit(app, _child(0.95))
    credential = grant(
        project, principal_id="agent-x02", rights=("execute", "read"), capability_id="cap-x02"
    )
    return Shared(project, revision_id, source.job_id, credential)


@pytest.mark.parametrize("transport", ["python", "cli", "http", "mcp"])
def test_g6_every_transport_accepts_warm_start_and_refuses_a1(
    shared: Shared, transport: str, tmp_path: Path
) -> None:
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

    capability, token = shared.grant
    client: Client
    with pytest.MonkeyPatch.context() as patch:
        if transport == "cli":
            out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", err)
            client = CliClient(shared.project, tmp_path / "raw.bin", out, err)
        elif transport == "python":
            client = PythonInline(shared.project)
        elif transport == "http":
            client = HttpClient(shared.project, token)
        else:
            client = McpClient(shared.project, capability)
        try:
            body = {"revision_id": shared.revision_id, "warm_start": {"job_id": "job-999999"}}
            request = {"operation": "solve", "idempotency_key": f"a1-{transport}", "body": body}
            error, refusal = client.call("submit_job", request)
            assert error, refusal
            assert (refusal["code"], refusal["message"]) == (
                "invalid_request",
                "warm_start_source_missing(job-999999)",
            )
            assert refusal["detail"]["pointer"] == "/body/warm_start/job_id"
            body = {
                "revision_id": shared.revision_id,
                "warm_start": {"job_id": shared.source_job_id},
            }
            request = {"operation": "solve", "idempotency_key": f"g6-{transport}", "body": body}
            error, submitted = client.call("submit_job", request)
            assert not error, submitted
            assert submitted["job"]["request"]["body"]["warm_start"] == {
                "job_id": shared.source_job_id
            }
            job_id = submitted["job"]["job_id"]
            waited: dict[str, Any] = {"ended": False}
            while not waited["ended"]:
                error, waited = client.call("wait_job", {"job_id": job_id, "timeout_s": 60})
                assert not error, waited
            error, result = client.call("get_job_result", {"job_id": job_id})
            assert not error, result
        finally:
            client.close()
    run = result["run_result"]
    assert (run["outcome"], run["verification_status"]) == ("CONVERGED", "VERIFIED")
    recorded = _read(shared.project / "jobs" / job_id / "bundle")["solve-path.json"]["warm_start"]
    assert (recorded["selection"], recorded["status"]) == (EXPLICIT, "accepted")
