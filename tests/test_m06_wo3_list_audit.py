"""M06 WO-3: `list_audit`, the agent history (Ask 4).

Design note `docs/design/M06-web-shell.md` §4.3, risk R2, gate G6; ADR 0019 Amendment 3, A3.3.
The first tests are R2's precondition: the idempotency key is inside the hashed request of both
keyed operations, so the audit/ledger join on `(principal_id, operation, request_sha256)` names
exactly one key. Then G6: the authorization matrix (own rows with `read`; another principal's or
all principals' rows need `policy` too, and a refusal is audited), every allowed `commit_change`
and `submit_job` row carrying its key, a limit-1 walk reproducing the whole sequence, descending
the reverse of ascending, and a cursor of the other order refused at `/cursor`.

The project mirrors the W26 fixture project's principals (§8): `agent-a` (read, draft, execute),
`viewer-b` (read), `supervisor-c` (read, policy).
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.authz import OPERATION_RIGHTS, authorize, grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import (
    SCHEMA_BASE,
    AuditRecord,
    CapabilityReference,
    Change,
    Edit,
    JobRequest,
    SolveBody,
    schema_errors,
)
from openflowsheet.canonical import canonical_json, document_sha256

NOMINAL = "SYN-001-nominal"
PAGE_SCHEMA = "application-results.schema.json#/$defs/audit_page"
RECORD_MEMBERS = {
    "seq",
    "at",
    "principal_id",
    "capability_id",
    "operation",
    "outcome",
    "code",
    "request_sha256",
    "effect",
    "idempotency_key",
}


# -- R2: the precondition (test it first) ---------------------------------------------------------


def test_r2_a_change_sets_key_is_inside_its_hash() -> None:
    change = Change(edits=(Edit("set", ("title",), "t"),))
    one = change.as_change_set("rev-000001", "key-one")
    two = change.as_change_set("rev-000001", "key-two")
    assert {key: value for key, value in one.items() if key != "idempotency_key"} == {
        key: value for key, value in two.items() if key != "idempotency_key"
    }
    assert document_sha256(one) != document_sha256(two)


def test_r2_a_job_requests_key_is_inside_its_hash() -> None:
    body = SolveBody(revision_id="rev-000001", policy_id="default")
    one = JobRequest(operation="solve", idempotency_key="key-one", body=body)
    two = JobRequest(operation="solve", idempotency_key="key-two", body=body)
    assert one.as_document()["body"] == two.as_document()["body"]
    assert one.request_sha256 != two.request_sha256


def test_r2_the_stored_hashes_are_the_ledgers_and_name_one_key(tmp_path: Path) -> None:
    """Through the store: the audit row and the ledger row of a commit and of a submit carry one
    `request_sha256`, and two equal requests under two keys hash apart."""
    with LocalApplication.create(tmp_path / "p", project_id="m06-r2") as app:
        revision = commit(app, CORPUS[NOMINAL]())
        edit = Change(edits=(Edit("set", ("title",), "same edit"),))
        first = app.commit_change(edit, revision, "same-edit-1")
        assert first.status == "committed"
        for key in ("same-solve-1", "same-solve-2"):
            app.submit_job(
                JobRequest(
                    operation="solve",
                    idempotency_key=key,
                    body=SolveBody(revision_id=revision, policy_id="default"),
                )
            )
        with app.store.reading() as connection:
            ledger = connection.execute(
                "SELECT principal_id, operation, idempotency_key, request_sha256 FROM ledger"
            ).fetchall()
        audit = app.store.audit_rows()
    triples = [(p, o, h) for p, o, _, h in ledger]
    assert len(triples) == len(set(triples)) == 4
    allowed = {
        (row["principal_id"], row["operation"], row["request_sha256"])
        for row in audit
        if row["outcome"] == "allowed" and row["operation"] in ("commit_change", "submit_job")
    }
    assert allowed == set(triples)


# -- the project ----------------------------------------------------------------------------------


class Project:
    def __init__(self, root: Path) -> None:
        self.path = root / "project"
        LocalApplication.create(self.path, project_id="m06-wo3").close()
        self.agent, _ = grant(
            self.path,
            principal_id="agent-a",
            rights=("read", "draft", "execute"),
            capability_id="cap-agent-a",
        )
        self.viewer, _ = grant(
            self.path, principal_id="viewer-b", rights=("read",), capability_id="cap-viewer-b"
        )
        self.supervisor, _ = grant(
            self.path,
            principal_id="supervisor-c",
            rights=("read", "policy"),
            capability_id="cap-supervisor-c",
        )

    def open(self, capability: CapabilityReference) -> LocalApplication:
        return LocalApplication.open(self.path, capability=capability)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Project]:
    built = Project(tmp_path_factory.mktemp("m06-wo3"))
    with built.open(built.agent) as agent:
        revision = commit(agent, CORPUS[NOMINAL]())
        agent.commit_change(
            Change(edits=(Edit("set", ("title",), "retitled"),)), revision, "agent-retitle"
        )
        for key in ("agent-solve-1", "agent-solve-2"):
            agent.submit_job(
                JobRequest(
                    operation="solve",
                    idempotency_key=key,
                    body=SolveBody(revision_id=revision, policy_id="default"),
                )
            )
        replayed = agent.submit_job(
            JobRequest(
                operation="solve",
                idempotency_key="agent-solve-1",
                body=SolveBody(revision_id=revision, policy_id="default"),
            )
        )
        assert replayed.replayed
    with built.open(built.viewer) as viewer:
        with pytest.raises(ApplicationError):
            viewer.submit_job(
                JobRequest(
                    operation="solve",
                    idempotency_key="viewer-solve",
                    body=SolveBody(revision_id=revision, policy_id="default"),
                )
            )
    yield built


def _walk(app: LocalApplication, **arguments: Any) -> list[AuditRecord]:
    """Every page of `list_audit(**arguments)`, followed by its cursors."""
    records: list[AuditRecord] = []
    cursor = None
    while True:
        page = app.list_audit(cursor=cursor, **arguments)
        records.extend(page.items)
        if page.next_cursor is None:
            return records
        cursor = page.next_cursor


def _refusal(call: Any) -> dict[str, Any]:
    with pytest.raises(ApplicationError) as refused:
        call()
    return refused.value.error.as_document()


# -- the operation --------------------------------------------------------------------------------


def test_the_row_and_its_right() -> None:
    row = OPERATIONS["list_audit"]
    assert (row.right, row.http, row.transports, row.mcp_tool, row.description_file) == (
        "read",
        ("GET", "/v1/audit"),
        ("python", "cli", "http"),
        None,
        None,
    )
    assert OPERATION_RIGHTS["list_audit"] == "read"
    assert row.response_schema == {
        "$ref": f"{SCHEMA_BASE}application-results.schema.json#/$defs/audit_page"
    }


def test_authorize_reads_the_target_principal_for_list_audit(project: Project) -> None:
    """D4 as amended: `cancel_job`'s rule, exactly."""
    for capability, own in ((project.agent, "agent-a"), (project.viewer, "viewer-b")):
        assert authorize(capability, "list_audit", own).allowed
        for other in ("supervisor-c", None):
            decision = authorize(capability, "list_audit", other)
            assert (decision.allowed, decision.code, decision.required) == (
                False,
                "forbidden",
                ("read", "policy"),
            )
    for other in ("agent-a", None):
        assert authorize(project.supervisor, "list_audit", other).allowed
    assert authorize(project.supervisor, "list_audit", "supervisor-c").required == ("read",)


# -- G6 -------------------------------------------------------------------------------------------


def test_g6_own_rows_with_read_are_allowed(project: Project) -> None:
    with project.open(project.viewer) as viewer:
        own = _walk(viewer, principal_id="viewer-b")
    assert own and {record.principal_id for record in own} == {"viewer-b"}
    assert [record.operation for record in own if record.outcome == "refused"][0] == "submit_job"


@pytest.mark.parametrize("target", ["agent-a", None])
def test_g6_other_or_all_principals_without_policy_are_forbidden_and_audited(
    project: Project, target: str | None
) -> None:
    with project.open(project.viewer) as viewer:
        before = len(_walk(viewer, principal_id="viewer-b"))
        error = _refusal(lambda: viewer.list_audit(principal_id=target))
        after = _walk(viewer, principal_id="viewer-b")
    assert error["code"] == "forbidden"
    assert error["detail"]["required"] == ["read", "policy"]
    assert len(after) == before + 1
    last = after[-1]
    assert (last.operation, last.outcome, last.code) == ("list_audit", "refused", "forbidden")


def test_g6_with_policy_every_principal_is_allowed(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        everyone = _walk(supervisor)
        agent = _walk(supervisor, principal_id="agent-a")
    assert {"agent-a", "viewer-b"} <= {record.principal_id for record in everyone}
    assert [r for r in everyone if r.principal_id == "agent-a"] == agent


def test_g6_every_allowed_commit_and_submit_carries_its_key(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        everyone = _walk(supervisor)
    keyed = [
        r
        for r in everyone
        if r.outcome == "allowed" and r.operation in ("commit_change", "submit_job")
    ]
    assert len(keyed) == 4  # two commits, two accepted submits (the replay adds no row)
    assert all(record.idempotency_key is not None for record in keyed)
    assert [r.idempotency_key for r in keyed if r.operation == "submit_job"] == [
        "agent-solve-1",
        "agent-solve-2",
    ]
    assert [r.idempotency_key for r in keyed if r.operation == "commit_change"][1] == (
        "agent-retitle"
    )
    # Refusals and the other effects carry none.
    assert all(
        r.idempotency_key is None
        for r in everyone
        if r.outcome == "refused" or r.operation not in ("commit_change", "submit_job")
    )


def test_g6_a_limit_1_walk_reproduces_the_sequence_and_descending_reverses_it(
    project: Project,
) -> None:
    with project.open(project.supervisor) as supervisor:
        whole = supervisor.list_audit(limit=200)
        assert whole.next_cursor is None
        ascending = list(whole.items)
        ones = _walk(supervisor, limit=1)
        descending = _walk(supervisor, order="descending", limit=3)
    # Each walk refuses nothing, and so adds no row of its own between the reads.
    assert [r.seq for r in ones] == [r.seq for r in ascending]
    assert ones == ascending
    assert descending == ascending[::-1]
    assert [r.seq for r in ascending] == sorted(r.seq for r in ascending)
    assert len({r.seq for r in ascending}) == len(ascending)


def test_g6_a_cursor_of_the_other_order_is_invalid(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        page = supervisor.list_audit(limit=1)
        assert page.next_cursor is not None
        error = _refusal(lambda: supervisor.list_audit(order="descending", cursor=page.next_cursor))
        assert (error["code"], error["detail"]["pointer"]) == ("invalid_request", "/cursor")
        for forged in ("not-a-cursor", _cursor({"order": "ascending"}), _cursor({"seq": 1})):
            error = _refusal(lambda: supervisor.list_audit(cursor=forged))  # noqa: B023
            assert (error["code"], error["detail"]["pointer"]) == ("invalid_request", "/cursor")


def _cursor(document: Any) -> str:
    return base64.urlsafe_b64encode(canonical_json(document)).decode("ascii").rstrip("=")


def test_the_cursor_is_order_and_seq(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        page = supervisor.list_audit(limit=2)
        assert page.next_cursor == _cursor({"order": "ascending", "seq": page.items[-1].seq})
        down = supervisor.list_audit(order="descending", limit=2)
        assert down.next_cursor == _cursor({"order": "descending", "seq": down.items[-1].seq})


def test_the_operation_filter(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        submits = _walk(supervisor, operation="submit_job")
        everyone = _walk(supervisor)
    assert submits == [r for r in everyone if r.operation == "submit_job"]
    assert {r.outcome for r in submits} == {"allowed", "refused"}


def test_the_response_through_dispatch_is_schema_valid(project: Project) -> None:
    with project.open(project.supervisor) as supervisor:
        page = dispatch(supervisor, "list_audit", {"limit": 3})
        assert schema_errors(PAGE_SCHEMA, page) == []
        assert all(set(item) == RECORD_MEMBERS for item in page["items"])
        own = dispatch(supervisor, "list_audit", {"principal_id": "supervisor-c"})
        assert schema_errors(PAGE_SCHEMA, own) == []
        for request, pointer in (
            ({"order": "up"}, "/order"),
            ({"limit": 0}, "/limit"),
            ({"limit": 201}, "/limit"),
            ({"operation": ""}, "/operation"),
            ({"principal_id": "has space"}, "/principal_id"),
        ):
            with pytest.raises(ApplicationError) as refused:
                dispatch(supervisor, "list_audit", request)
            error = refused.value.error
            assert (error.code, error.detail["pointer"]) == ("invalid_request", pointer), request
