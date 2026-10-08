"""T07 W6a: the HTTP binding (`application/bindings/http.py`) adds nothing to `dispatch`.

Design note `docs/design/T07-jobs-and-bindings.md` §4.3 (routes), §5.8 and ruling round 4 (the
status of each `ApiError` code), §10.2 (the bearer credential), §11.2 (HTTP specifics), §11.6
(how a transport is proved to add nothing) and §16 G14:

- **G14, HTTP's half.** The bijection between the HTTP rows of `OPERATIONS` and the Starlette
  routes; the import-graph lint of every module under `bindings/`; and a scenario — every
  HTTP-exposed operation's success path, effects included, and the refusals a transport can
  reach — run once through Starlette's `TestClient` on one fresh project and once through
  `dispatch` as the same principal on another, with equal responses (volatile clock members
  removed; ids agree because a fresh store's ordinals are deterministic).
- **Authorization over HTTP**: no or a bad credential is 401, missing rights 403, and a revoked
  or expired grant is refused on its next call.
- **The request document**: a non-canonical body (NaN, 2⁵³ + 1, a repeated key) is 422
  `document_not_canonical` before any method runs, and audited; so are the transport's own
  refusals (size, media type, JSON, a member given twice); the reserved `auto:` key is refused.

The binding tests need the `server` extra and skip without it, as `test_t07_server_extra.py`'s
marker does; the import-graph lint reads source only and always runs.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS

from openflowsheet.application.authz import grant, new_token, revoke
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import API_ERROR_HTTP_STATUS, schema_errors
from openflowsheet.canonical import canonical_json

NOMINAL = "SYN-001-nominal"
PROJECT_ID = "w6a-http"
PRINCIPAL = "agent-http"
CAPABILITY = "cap-agent-http"
BINDINGS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings"
#: §11.6 (2): what a binding may import, besides the standard library.
ALLOWED_APPLICATION = {
    "openflowsheet.application.contract",
    "openflowsheet.application.types",
    "openflowsheet.application.operations",
    "openflowsheet.application.projection",
}
#: `anyio` too: §11.3 names `anyio.to_thread.run_sync`, the SDK's own dependency (W6b decision).
ALLOWED_THIRD_PARTY = {"starlette", "uvicorn", "mcp", "anyio"}
#: §11.6 (3): the members compared after removal — clock readings and host facts.
VOLATILE = {
    "at",  # an audit row's clock reading (ADR 0019 Amendment 3, `list_audit`)
    "recorded_at",
    "created_at",
    "started_at",
    "ended_at",
    "elapsed_seconds",
    "hostname",
    "environment",
    "timestamp",
}
#: Artifacts whose bytes hold a clock reading: the run manifest, and the bundle that holds it.
CLOCKED_KINDS = {"run_manifest", "replay_bundle"}
#: Starlette 1.x warns that its test client will move to `httpx2`; the pinned extra has `httpx`.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)

Call = Callable[[str, dict[str, Any]], tuple[int, Any]]


# ================================================================ the import-graph lint (§11.6)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative import"
            assert node.module is not None
            found.append(node.module)
    return found


@pytest.mark.parametrize("module", sorted(p.name for p in BINDINGS.glob("*.py")))
def test_a_binding_imports_only_the_dispatch_surface(module: str) -> None:
    for name in _imports(BINDINGS / module):
        top = name.split(".")[0]
        if name == "__future__" or top in sys.stdlib_module_names:
            continue
        if top in ALLOWED_THIRD_PARTY:
            continue
        assert name in ALLOWED_APPLICATION, f"{module} imports {name}"


def test_the_lint_sees_the_http_module_and_would_catch_a_violation(tmp_path: Path) -> None:
    assert "openflowsheet.application.operations" in _imports(BINDINGS / "http.py")
    bad = tmp_path / "bad.py"
    bad.write_text("from openflowsheet.application.local import LocalApplication\n")
    assert _imports(bad) == ["openflowsheet.application.local"]
    assert "openflowsheet.application.local" not in ALLOWED_APPLICATION


# ==================================================================================== fixtures


@pytest.fixture(scope="module")
def http() -> Any:
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from openflowsheet.application.bindings import http as module

    return module


class Served:
    """One project, its owner, a grant's token, and a `TestClient` over the owner."""

    def __init__(
        self,
        http: Any,
        directory: Path,
        rights: tuple[str, ...] = ("draft", "execute", "read"),
        *,
        policy_of: Served | None = None,
    ) -> None:
        """`policy_of`: take that project's policy file and token, so the two projects' policy
        hashes (recorded on every job) are equal."""
        from starlette.testclient import TestClient

        self.directory = directory
        self.owner = LocalApplication.create(directory, project_id=PROJECT_ID)
        if policy_of is None:
            self.capability, self.token = grant(
                directory, principal_id=PRINCIPAL, rights=rights, capability_id=CAPABILITY
            )
        else:
            policy = self.owner.store.policy_path
            assert policy is not None and policy_of.owner.store.policy_path is not None
            policy.write_bytes(policy_of.owner.store.policy_path.read_bytes())
            self.capability, self.token = policy_of.capability, policy_of.token
            assert self.owner.policy == policy_of.owner.policy
        self.client = TestClient(http.create_app(self.owner), raise_server_exceptions=False)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def view(self) -> LocalApplication:
        view = self.owner.authenticated(self.token)
        assert view is not None
        return view

    def close(self) -> None:
        self.client.close()
        self.owner.close()

    def head(self) -> str | None:
        with self.owner.store.reading() as connection:
            return self.owner.store.head(connection)

    def refusals(self) -> list[tuple[str, str | None]]:
        return [
            (row["operation"], row["code"])
            for row in self.owner.store.audit_rows()
            if row["outcome"] == "refused"
        ]


@pytest.fixture
def served(http: Any, tmp_path: Path) -> Iterator[Served]:
    project = Served(http, tmp_path / "project")
    yield project
    project.close()


def _url(name: str, request: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """`(verb, url, remaining members)`: the path parameters substituted, percent-encoded as a
    single segment each."""
    http = OPERATIONS[name].http
    assert http is not None
    verb, path = http
    remaining = dict(request)
    for member in list(remaining):
        marker = "{" + member + "}"
        if marker in path:
            path = path.replace(marker, quote(str(remaining.pop(member)), safe=""))
    assert "{" not in path, (name, path)
    return verb, path, remaining


def _query(value: Any) -> str:
    return json.dumps(value) if isinstance(value, bool | int | float) else str(value)


def http_call(served: Served, name: str, request: dict[str, Any]) -> tuple[int, Any]:
    """One operation over HTTP, as a client that knows only §4.3's table would make it."""
    verb, path, remaining = _url(name, request)
    if verb == "GET":
        params = {member: _query(value) for member, value in remaining.items()}
        response = served.client.get(path, params=params, headers=served.headers)
    else:
        body = json.dumps(remaining).encode() if remaining else b""
        headers = {**served.headers, "Content-Type": "application/json"}
        response = served.client.post(path, content=body, headers=headers)
    if response.headers.get("content-type", "").startswith("application/octet-stream"):
        return response.status_code, response.content
    return response.status_code, response.json()


def direct_call(view: LocalApplication, name: str, request: dict[str, Any]) -> tuple[int, Any]:
    """The same operation through `dispatch`, with a refusal read as HTTP would carry it."""
    try:
        return 200, dispatch(view, name, request)
    except ApplicationError as refused:
        return refused.error.http_status, refused.error.as_document()


def _stable(document: Any) -> Any:
    """`document` without its clock readings. A run manifest records its clock and host, so
    the digest and size of a reference to it, or to the bundle holding it, go too (G6's
    "except volatile manifest fields")."""
    if isinstance(document, dict):
        if document.get("kind") in CLOCKED_KINDS and "artifact_id" in document:
            document = {k: v for k, v in document.items() if k not in ("sha256", "size_bytes")}
        return {k: _stable(v) for k, v in document.items() if k not in VOLATILE}
    if isinstance(document, list):
        return [_stable(item) for item in document]
    return document


def _seq_aligned(document: Any, offset: int) -> Any:
    """A `list_audit` page with every `seq`, and its cursor's, moved back by `offset`; any other
    document as it is."""
    items = document.get("items") if isinstance(document, dict) else None
    if not (isinstance(items, list) and items and all("seq" in item for item in items)):
        return document
    aligned = [{**item, "seq": item["seq"] - offset} for item in items]
    cursor = document["next_cursor"]
    if cursor is not None:
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        moved = {**decoded, "seq": decoded["seq"] - offset}
        cursor = base64.urlsafe_b64encode(canonical_json(moved)).decode("ascii").rstrip("=")
    return {**document, "items": aligned, "next_cursor": cursor}


# ========================================================================= G14: the bijection


def test_the_routes_are_the_http_rows_of_the_table(http: Any, served: Served) -> None:
    routes = served.client.app.routes
    assert [route.name for route in routes] == [
        name for name, row in OPERATIONS.items() if "http" in row.transports
    ]
    served_pairs = {(verb, route.path) for route in routes for verb in route.methods}
    table_pairs = {row.http for row in OPERATIONS.values() if "http" in row.transports}
    assert served_pairs == table_pairs
    assert all(len(route.methods) == 1 for route in routes), "no implicit HEAD"
    assert {"solve", "reproduce"}.isdisjoint(route.name for route in routes)
    assert "artifact_bytes" in {route.name for route in routes}


# ========================================================================= G14: the scenario


def _scenario(call: Call, raw: Callable[[str, bytes], tuple[int, Any]]) -> list[tuple[int, Any]]:
    """Every HTTP operation's success path, effects included, then the refusals a transport can
    reach. `raw(path, body)` posts a body as bytes (a non-canonical one)."""
    out: list[tuple[int, Any]] = []

    def step(name: str, request: dict[str, Any]) -> Any:
        status, document = call(name, request)
        out.append((status, document))
        return document

    nominal = CORPUS[NOMINAL]()
    edits = [{"operation": "set", "path": [k], "value": v} for k, v in nominal.items()]
    first = step(
        "commit_change", {"edits": edits, "expected_revision": None, "idempotency_key": "a"}
    )
    revision = first["revision_id"]
    title = [{"operation": "set", "path": ["title"], "value": "y"}]
    step("validate", {"revision_id": revision, "task": "simulation"})
    step("preview_change", {"edits": title, "expected_revision": revision})
    second = {"edits": title, "expected_revision": revision, "idempotency_key": "b"}
    step("commit_change", second)
    step("commit_change", second)  # replayed
    step("commit_change", {**second, "edits": [{**title[0], "value": "z"}]})  # 409
    solve = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}}
    job_id = step("submit_job", solve)["job"]["job_id"]
    step("submit_job", solve)  # replayed
    step("get_job", {"job_id": job_id})
    step("list_jobs", {"limit": 1})
    step("list_job_events", {"job_id": job_id, "after_sequence": 0, "limit": 3})
    step("wait_job", {"job_id": job_id, "timeout_s": 0})
    step("get_job_result", {"job_id": job_id})
    step("cancel_job", {"job_id": job_id})  # already ended: the job, unchanged
    step("get_project", {})
    step("list_models", {})
    page = step("list_revisions", {"limit": 1})
    step("list_revisions", {"limit": 1, "cursor": page["next_cursor"]})
    step("get_revision", {"revision_id": revision, "pointer": "/connections", "limit": 2})
    step(
        "diff_revisions",
        {"from_revision": revision, "to_revision": page["items"][0]["revision_id"]},
    )
    step("inspect_structure", {"revision_id": revision, "depth": 2})
    state = f"{job_id}:bundle/solution-state.json"
    step("get_artifact", {"artifact_id": state, "pointer": "/variable_ids", "limit": 5})
    step("artifact_bytes", {"artifact_id": state})
    # ADR 0019 Amendment 3 (A3.3): the grant's own audit rows, paged; every principal's needs
    # `policy`, which the grant does not hold (403, audited).
    audit = step("list_audit", {"principal_id": PRINCIPAL, "limit": 2})
    step("list_audit", {"principal_id": PRINCIPAL, "limit": 2, "cursor": audit["next_cursor"]})
    step("list_audit", {"principal_id": PRINCIPAL, "order": "descending", "limit": 3})
    step("list_audit", {})  # 403
    step("list_audit", {"order": "descending", "cursor": audit["next_cursor"]})  # 403 first
    step(
        "list_audit",
        {"principal_id": PRINCIPAL, "order": "descending", "cursor": audit["next_cursor"]},
    )  # 422 the other order's cursor
    # Refusals a transport can reach.
    step("get_job", {"job_id": "job-999999"})  # 404
    step("get_artifact", {"artifact_id": "job-999999:bundle"})  # 404
    step("get_revision", {"revision_id": revision, "depth": 99})  # 422 schema
    step("list_revisions", {"cursor": "not-a-cursor"})  # 422
    step("submit_job", {**solve, "idempotency_key": "auto:mine"})  # 422 reserved key
    step("commit_change", {**second, "idempotency_key": "auto:mine"})  # 422 reserved key
    step("get_job_result", {"job_id": "job-999999"})  # 404
    for literal in (b"NaN", b"9007199254740993"):  # 422 document_not_canonical
        body = b'{"edits":[{"operation":"set","path":["title"],"value":%s}],' % literal
        out.append(raw("/v1/changes", body + b'"expected_revision":null,"idempotency_key":"n"}'))
    return out


def test_g14_every_http_operation_equals_dispatch_as_the_same_principal(
    http: Any, tmp_path: Path
) -> None:
    over_http = Served(http, tmp_path / "http")
    in_process = Served(http, tmp_path / "direct", policy_of=over_http)
    try:
        view = in_process.view()
        assert (view.principal_id, view.capability_id) == (PRINCIPAL, CAPABILITY)

        def raw_http(path: str, body: bytes) -> tuple[int, Any]:
            headers = {**over_http.headers, "Content-Type": "application/json"}
            response = over_http.client.post(path, content=body, headers=headers)
            return response.status_code, response.json()

        def raw_direct(path: str, body: bytes) -> tuple[int, Any]:
            assert path == "/v1/changes"
            return direct_call(view, "commit_change", json.loads(body))

        # The twin's policy is copied, not granted, so its audit lacks the grant's row: its
        # `seq` runs behind by a constant, which `_seq_aligned` removes (and checks).
        offset = len(over_http.owner.store.audit_rows()) - len(in_process.owner.store.audit_rows())
        assert offset == 1
        got = _scenario(lambda n, r: http_call(over_http, n, r), raw_http)
        expected = _scenario(lambda n, r: direct_call(view, n, r), raw_direct)
        assert len(got) == len(expected)
        got = [(status, _seq_aligned(document, offset)) for status, document in got]
        served_names = {n for n, row in OPERATIONS.items() if "http" in row.transports}
        assert len(served_names) == 19  # with ADR 0019 Amendment 3's `list_audit`
        for index, ((status, document), (want_status, want)) in enumerate(
            zip(got, expected, strict=True)
        ):
            assert status == want_status, (index, document)
            assert _stable(document) == _stable(want), index
            if status != 200:
                assert schema_errors("api-error.schema.json", document) == []
                assert status == API_ERROR_HTTP_STATUS[document["code"]]
        codes = [document["code"] for status, document in got if status != 200]
        assert set(codes) == {
            "idempotency_key_reused",
            "not_found",
            "invalid_request",
            "document_not_canonical",
            "forbidden",  # `list_audit` of every principal without `policy` (ADR 0019 A3.3)
        }
        # The same refusals were audited on both sides, in the same order.
        assert over_http.refusals() == in_process.refusals()
        assert over_http.head() == in_process.head()
    finally:
        over_http.close()
        in_process.close()


# ================================================================ the raw export and its route


def test_the_raw_export_streams_the_stored_bytes_with_their_digest(served: Served) -> None:
    revision = http_call(
        served,
        "commit_change",
        {
            "edits": [
                {"operation": "set", "path": [k], "value": v} for k, v in CORPUS[NOMINAL]().items()
            ],
            "expected_revision": None,
            "idempotency_key": "a",
        },
    )[1]["revision_id"]
    job = http_call(
        served,
        "submit_job",
        {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}},
    )[1]["job"]
    state = f"{job['job_id']}:bundle/solution-state.json"
    row = served.owner.store.artifact(state)
    assert row is not None
    stored = (served.owner.files_root / row.relpath).read_bytes()
    response = served.client.get(
        f"/v1/artifacts/{quote(state, safe='')}/raw", headers=served.headers
    )
    assert response.status_code == 200
    assert response.content == stored
    digest = hashlib.sha256(stored).hexdigest()
    assert response.headers["X-Content-SHA256"] == digest
    assert response.headers["content-length"] == str(len(stored))
    projection = http_call(served, "get_artifact", {"artifact_id": state, "depth": 1})[1]
    assert projection["sha256"] == digest
    # The id's '/' sent unencoded is another path: no route, and the answer says how to send it.
    response = served.client.get(f"/v1/artifacts/{state}/raw", headers=served.headers)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "%2F" in response.json()["message"]
    # A bundle is a directory: its raw export is refused as the method refuses it.
    status, document = http_call(
        served, "artifact_bytes", {"artifact_id": f"{job['job_id']}:bundle"}
    )
    assert (status, document["code"]) == (501, "unsupported")


# ============================================================================= authorization


def test_no_credential_or_a_bad_one_is_401(served: Served) -> None:
    for headers in (
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer prt_short"},
        {"Authorization": f"Bearer {new_token()}"},
        {"Authorization": f"Bearer {served.token}x"},
    ):
        response = served.client.get("/v1/project", headers=headers)
        assert response.status_code == 401, headers
        assert response.json()["code"] == "unauthenticated"
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert schema_errors("api-error.schema.json", response.json()) == []
    # The scheme is case-insensitive (RFC 7235 §2.1).
    lower = served.client.get("/v1/project", headers={"Authorization": f"bearer {served.token}"})
    assert lower.status_code == 200


def test_insufficient_rights_are_403(http: Any, tmp_path: Path) -> None:
    reader = Served(http, tmp_path / "reader", rights=("read",))
    try:
        assert http_call(reader, "get_project", {})[0] == 200
        change = {
            "edits": [{"operation": "set", "path": ["title"], "value": "t"}],
            "expected_revision": None,
            "idempotency_key": "k",
        }
        status, document = http_call(reader, "commit_change", change)
        assert (status, document["code"]) == (403, "forbidden")
        assert document["detail"]["required"] == ["draft"]
        status, document = http_call(
            reader,
            "submit_job",
            {"operation": "solve", "idempotency_key": "k", "body": {"revision_id": "r"}},
        )
        assert (status, document["code"]) == (403, "forbidden")
        assert reader.head() is None
        assert ("commit_change", "forbidden") in reader.refusals()
    finally:
        reader.close()


def test_a_revoked_token_is_refused_on_its_next_call(served: Served) -> None:
    assert http_call(served, "get_project", {})[0] == 200
    revoke(served.directory, CAPABILITY)
    status, document = http_call(served, "get_project", {})
    assert (status, document["code"]) == (401, "unauthenticated")
    # A view taken before the revocation is re-resolved on its next call as well.
    fresh_capability, fresh_token = grant(
        served.directory, principal_id="second", capability_id="cap-second"
    )
    view = served.owner.authenticated(fresh_token)
    assert view is not None and view.principal_id == "second"
    revoke(served.directory, fresh_capability.capability_id)
    with pytest.raises(ApplicationError) as refused:
        dispatch(view, "get_project", {})
    assert refused.value.code == "unauthenticated"


def test_an_expired_token_is_401(served: Served) -> None:
    _, token = grant(
        served.directory,
        principal_id="late",
        capability_id="cap-late",
        expires_at="2020-01-01T00:00:00.000000Z",
    )
    response = served.client.get("/v1/project", headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, response.json()["code"]) == (401, "unauthenticated")


def test_the_owner_view_is_the_grant_and_shares_the_owner(served: Served) -> None:
    view = served.view()
    assert (view.principal_id, view.capability_id) == (PRINCIPAL, CAPABILITY)
    assert view.store is served.owner.store
    assert view.executor is served.owner.executor
    assert view.owner_instance == served.owner.owner_instance
    assert served.owner.principal_id == "local-owner", "the owner itself is unchanged"
    assert served.owner.authenticated(new_token()) is None
    assert served.owner.authenticated("") is None


# ====================================================================== the request document


def _post(served: Served, path: str, body: bytes, content_type: str = "application/json") -> Any:
    headers = {**served.headers, "Content-Type": content_type}
    return served.client.post(path, content=body, headers=headers)


def test_a_non_canonical_body_is_422_before_any_method_runs(served: Served) -> None:
    prefix = b'{"edits":[{"operation":"set","path":["title"],"value":'
    suffix = b'}],"expected_revision":null,"idempotency_key":"k"}'
    cases = {
        b"NaN": "/edits/0/value",
        b"Infinity": "/edits/0/value",
        b"-Infinity": "/edits/0/value",
        b"9007199254740993": "/edits/0/value",
        b"-9007199254740993": "/edits/0/value",
        b"1e400": "/edits/0/value",
        b'"\\ud800"': "/edits/0/value",
    }
    for literal, pointer in cases.items():
        response = _post(served, "/v1/changes", prefix + literal + suffix)
        assert response.status_code == 422, literal
        assert response.json()["code"] == "document_not_canonical", literal
        assert response.json()["detail"]["pointer"] == pointer, literal
    repeated = {
        b'{"idempotency_key":"a","idempotency_key":"b","edits":[],"expected_revision":null}': (
            "/idempotency_key"
        ),
        prefix + b'1,"value":2' + suffix: "/edits/0/value",
    }
    for body, pointer in repeated.items():
        response = _post(served, "/v1/changes", body)
        assert (response.status_code, response.json()["code"]) == (422, "document_not_canonical")
        assert response.json()["detail"]["pointer"] == pointer
    assert served.head() is None, "no method ran"
    refusals = served.refusals()
    assert refusals == [("commit_change", "document_not_canonical")] * (len(cases) + 2)


def test_the_transport_refuses_the_reserved_key_prefix(served: Served) -> None:
    for name, request in (
        (
            "submit_job",
            {"operation": "solve", "idempotency_key": "auto:x", "body": {"revision_id": "r"}},
        ),
        (
            "commit_change",
            {"edits": [], "expected_revision": None, "idempotency_key": "auto:x"},
        ),
    ):
        status, document = http_call(served, name, request)
        assert (status, document["code"]) == (422, "invalid_request"), name
        assert document["detail"]["pointer"] == "/idempotency_key"
    assert served.owner.store.job_ids() == ()
    assert served.head() is None


def test_the_transports_own_refusals_are_422_and_audited(served: Served) -> None:
    oversized = b'{"pad":"' + b"x" * (1 << 20) + b'"}'
    cases = [
        _post(served, "/v1/changes", oversized),
        _post(served, "/v1/changes", b"{}", "text/plain"),
        _post(served, "/v1/changes", b"{not json"),
        _post(served, "/v1/changes", b"\xff\xfe"),
        _post(served, "/v1/changes", b"[]"),
        _post(
            served, "/v1/revisions/rev-000001/validate", b'{"revision_id":"x","task":"simulation"}'
        ),
        served.client.get("/v1/revisions?limit=1&limit=2", headers=served.headers),
    ]
    for response in cases:
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "invalid_request"
        assert schema_errors("api-error.schema.json", response.json()) == []
    assert cases[5].json()["detail"]["pointer"] == "/revision_id"
    assert cases[6].json()["detail"]["pointer"] == "/limit"
    assert [code for _, code in served.refusals()] == ["invalid_request"] * len(cases)


def test_query_values_are_typed_by_the_request_schema(served: Served) -> None:
    ok = served.client.get("/v1/revisions?limit=3", headers=served.headers)
    assert ok.status_code == 200
    for query, pointer in (("limit=abc", "/limit"), ("limit=1.5", "/limit"), ("bogus=1", "")):
        response = served.client.get(f"/v1/revisions?{query}", headers=served.headers)
        assert (response.status_code, response.json()["code"]) == (422, "invalid_request"), query
        assert response.json()["detail"]["pointer"] == pointer, query
    # A cursor is a string whatever it looks like: the schema passes "12", and the method
    # refuses it as a cursor it never issued.
    response = served.client.get("/v1/revisions?cursor=12", headers=served.headers)
    assert (response.status_code, response.json()["detail"]) == (422, {"pointer": "/cursor"})
    assert "not one this list issued" in response.json()["message"]


def test_unknown_routes_and_methods_answer_in_the_one_error_shape(served: Served) -> None:
    for method, path, code in (
        ("POST", "/v1/solve", "not_found"),
        ("POST", "/v1/reproduce", "not_found"),
        ("GET", "/v1/nothing", "not_found"),
        ("GET", "/v1/project/", "not_found"),
        ("DELETE", "/v1/project", "invalid_request"),
        ("HEAD", "/v1/project", "invalid_request"),
        ("OPTIONS", "/v1/jobs", "invalid_request"),
    ):
        response = served.client.request(method, path, headers=served.headers)
        assert response.status_code == API_ERROR_HTTP_STATUS[code], (method, path)
        if method != "HEAD":
            assert response.json()["code"] == code, (method, path)
            assert schema_errors("api-error.schema.json", response.json()) == []
    # No CORS: a browser's preflight is refused like any other method, and names no origin.
    preflight = served.client.options(
        "/v1/jobs",
        headers={"Origin": "http://elsewhere.example", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 422
    assert not any(key.lower().startswith("access-control-") for key in preflight.headers)
    assert preflight.headers["Allow"] == "GET, POST"
    assert preflight.json()["detail"] == {"method": "OPTIONS", "allowed": "GET, POST"}


def test_an_untyped_exception_is_500_with_a_fixed_message(
    served: Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: LocalApplication) -> Any:
        raise RuntimeError("secret internals /home/someone/traceback")

    monkeypatch.setattr(LocalApplication, "get_project", broken)
    status, document = http_call(served, "get_project", {})
    assert (status, document["code"]) == (500, "internal_error")
    assert "secret" not in json.dumps(document)
    assert schema_errors("api-error.schema.json", document) == []


# =================================================================================== serving


def test_serve_binds_the_loopback_interface_unless_told_otherwise(http: Any) -> None:
    assert http.DEFAULT_HOST == "127.0.0.1"
    for host in ("127.0.0.1", "127.0.0.2", "::1", "localhost"):
        assert http.is_loopback(host), host
    for host in ("0.0.0.0", "::", "192.168.1.10", "example.org"):
        assert not http.is_loopback(host), host
        with pytest.raises(ValueError, match="allow_remote"):
            http.serve(object(), host=host)
