"""ST WO-3: the `get_stream_table` operation (design note `docs/design/ST-stream-table.md` §6.1,
ADR 0068; gates G11, G12).

One project holds the README Rankine cycle solved three times and MSG's corpus C01 (the same cycle
with the boiler at 973.15 K, which ends `INITIALIZATION_FAILED`). One converged bundle is served as
it is; one has its revision replaced by TH-C2's (`coolprop-heos-v1`, refused `unsupported` where the
extra is not installed); one has a state value changed after its hash was taken (`internal_error`).
Every §6.1 refusal is asserted to be one error document on Python, the CLI, HTTP and MCP; the
conformance scenario (`tests/test_t07_conformance.py`) adds `not_ready`, a job without a bundle and
an unknown job on all five of its clients.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import st_support
from conftest import REPO_ROOT
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application import stream_table
from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import STREAM_TABLE_DEPTH, LocalApplication
from openflowsheet.application.projection import MAX_DEPTH
from openflowsheet.application.types import Change, schema_errors
from openflowsheet.canonical import document_sha256
from openflowsheet.run.bundle import ARTIFACT_DIR

RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
TH_C2 = REPO_ROOT / "benchmarks" / "s11" / "thermal" / "TH-C2.json"
SCHEMA = "stream-table.schema.json"
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


def _change_set(boiler_t: float | None = None) -> dict[str, Any]:
    """The README Rankine change set; with `boiler_t`, MSG's corpus C01 (its boiler at 973.15 K)."""
    document: dict[str, Any] = json.loads(RANKINE.read_text(encoding="utf-8"))
    if boiler_t is not None:
        document["idempotency_key"] = "st-c01"
        for edit in document["edits"]:
            if edit["path"] == ["specifications"]:
                (spec,) = [s for s in edit["value"] if s["id"] == "boiler-T"]
                spec["value"] = boiler_t
    return document


@dataclass(frozen=True)
class Jobs:
    project: Path
    token: str
    capability: Any
    converged: str
    failed: str
    failed_bundle: str
    unsupported: str
    inconsistent: str

    def bundle(self, job_id: str) -> Path:
        return self.project / "jobs" / job_id / "bundle"


def _commit(app: LocalApplication, document: dict[str, Any], parent: str | None = None) -> str:
    change, _, key = Change.from_change_set(document)
    committed = app.commit_change(change, parent, key)
    assert committed.revision_id is not None
    return committed.revision_id


def _solve(app: LocalApplication, revision_id: str, expected: str) -> str:
    result = app.solve(revision_id, "default")
    assert result.outcome == expected, result.outcome
    return result.job_id


@pytest.fixture(scope="module")
def jobs(tmp_path_factory: pytest.TempPathFactory) -> Jobs:
    project = tmp_path_factory.mktemp("st-operation") / "project"
    with LocalApplication.create(project, project_id="st-operation") as app:
        rankine = _commit(app, _change_set())
        converged, unsupported, inconsistent = (_solve(app, rankine, "CONVERGED") for _ in range(3))
        c01 = _commit(app, _change_set(973.15), rankine)
        failed = _solve(app, c01, "INITIALIZATION_FAILED")
        failed_bundle = next(
            o.artifact_id for o in app.get_job(failed).outputs if o.kind == "replay_bundle"
        )
    capability, token = grant(project, principal_id="agent-st", rights=("read",))
    made = Jobs(
        project, token, capability, converged, failed, failed_bundle, unsupported, inconsistent
    )
    # TH-C2's revision (`coolprop-heos-v1`) in place of the bundle's.
    revision = made.bundle(unsupported) / ARTIFACT_DIR / "revision.json"
    revision.write_text(TH_C2.read_text(encoding="utf-8"), encoding="utf-8")
    # A state value changed after the state's hash was taken.
    state_path = made.bundle(inconsistent) / ARTIFACT_DIR / "solution-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    name = sorted(state["variables"])[0]
    state["variables"][name] = state["variables"][name] + 1.0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return made


@pytest.fixture
def clients(jobs: Jobs, tmp_path: Path) -> Iterator[dict[str, Client]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    made: dict[str, Client] = {
        "python": PythonInline(jobs.project),
        "cli": CliClient(jobs.project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(jobs.project, jobs.token),
        "mcp": McpClient(jobs.project, jobs.capability),
    }
    try:
        yield made
    finally:
        for client in made.values():
            client.close()


def _on_every_transport(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch, request: dict[str, Any]
) -> tuple[bool, Any]:
    """`get_stream_table(request)` on the four transports: one outcome, asserted equal."""
    client = clients["cli"]
    assert isinstance(client, CliClient)
    # The CLI client's streams, set in the test body: pytest's capture resets both between a
    # fixture's setup and the test's call.
    monkeypatch.setattr(sys, "stdout", client.out)
    monkeypatch.setattr(sys, "stderr", client.err)
    outcomes = {name: c.call("get_stream_table", request) for name, c in clients.items()}
    reference = outcomes["python"]
    for name, outcome in outcomes.items():
        assert outcome == reference, name
    return reference


# ======================================================================================= G11


def test_g11_the_table_is_one_document_on_every_transport(
    jobs: Jobs, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    error, whole = _on_every_transport(clients, monkeypatch, {"job_id": jobs.converged})
    assert not error, whole
    assert whole["subject_id"] == f"stream-table:{jobs.converged}"
    assert whole["truncated"] is False and whole["next_cursor"] is None
    document = whole["value"]
    assert document["schema_version"] == "stream-table-v1"
    assert document["verification_status"] == "VERIFIED"
    assert document["source"]["job_id"] == jobs.converged
    assert document["source"]["bundle_id"] == f"{jobs.converged}:bundle"
    assert whole["sha256"] == document_sha256(document)
    error, page = _on_every_transport(
        clients, monkeypatch, {"job_id": jobs.converged, "pointer": "/streams", "limit": 2}
    )
    assert not error, page
    assert page["sha256"] == whole["sha256"]
    assert page["value"] == document["streams"][:2]


def test_g11_a_run_without_a_solution_names_the_bundle_its_files_and_the_outcome(
    jobs: Jobs, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    error, refused = _on_every_transport(clients, monkeypatch, {"job_id": jobs.failed})
    assert error
    assert refused["code"] == "not_found"
    detail = dict(refused["detail"])
    explanation = detail.pop("explanation")
    members = detail.pop("members")
    assert detail == {
        "job_id": jobs.failed,
        "run_outcome": "INITIALIZATION_FAILED",
        "bundle_id": jobs.failed_bundle,
        "member": "solution-state.json",
    }
    assert "failure-bundle.json" in members and "solution-state.json" not in members
    assert explanation["summary"] == (
        f"Bundle '{jobs.failed_bundle}' has no file 'solution-state.json': its run ended "
        "INITIALIZATION_FAILED and wrote no solution."
    )


@pytest.mark.skipif(st_support.COOLPROP, reason="the coolprop extra is installed; TH-C2 is served")
def test_g11_an_unavailable_basis_is_unsupported_with_its_hint(
    jobs: Jobs, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    error, refused = _on_every_transport(clients, monkeypatch, {"job_id": jobs.unsupported})
    assert error
    assert (refused["code"], refused["message"]) == (
        "unsupported",
        "basis_unavailable(coolprop-heos-v1)",
    )
    assert refused["detail"]["job_id"] == jobs.unsupported
    assert refused["detail"]["hint"]


def test_g11_an_inconsistent_bundle_is_an_internal_error(
    jobs: Jobs, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    error, refused = _on_every_transport(clients, monkeypatch, {"job_id": jobs.inconsistent})
    assert error
    assert refused["code"] == "internal_error"
    assert refused["message"] == "the bundle's solution state and certificate are inconsistent"
    detail = dict(refused["detail"])
    detail.pop("explanation")
    assert detail == {
        "job_id": jobs.inconsistent,
        "bundle_id": f"{jobs.inconsistent}:bundle",
        "reasons": ["state_sha256_mismatch"],
    }


def test_g11_an_unknown_job_is_not_found(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    error, refused = _on_every_transport(clients, monkeypatch, {"job_id": "job-999999"})
    assert error and refused["code"] == "not_found"
    assert refused["message"] == "no such job"


# ============================================================================= Python level


def test_the_projection_is_from_bundle_of_the_jobs_bundle(jobs: Jobs) -> None:
    """§6.1: the document is `from_bundle` of the job's bundle with its `job_id` and `bundle_id`;
    `sha256` is its canonical hash, and the whole document fits the default depth."""
    bundle_id = f"{jobs.converged}:bundle"
    expected = stream_table.from_bundle(
        jobs.bundle(jobs.converged), source={"job_id": jobs.converged, "bundle_id": bundle_id}
    )
    with LocalApplication.open(jobs.project) as app:
        first = app.get_stream_table(jobs.converged)
        second = app.get_stream_table(jobs.converged)
    assert first == second
    assert first.value == expected
    assert first.sha256 == document_sha256(expected)
    assert schema_errors(SCHEMA, first.value) == []
    assert STREAM_TABLE_DEPTH == MAX_DEPTH == 12


def test_the_refusals_are_audited(jobs: Jobs) -> None:
    with LocalApplication.open(jobs.project) as app:
        with pytest.raises(ApplicationError) as refused:
            app.get_stream_table(jobs.failed)
        rows = app.list_audit(operation="get_stream_table", order="descending", limit=1).items
    assert refused.value.code == "not_found"
    assert [(row.outcome, row.code) for row in rows] == [("refused", "not_found")]
