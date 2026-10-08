"""M06 gate G2: every operation the web shell uses answers schema-valid over HTTP.

Design note `docs/design/M06-web-shell.md` §8 A1 and §11 G2. The W26 fixture project
(`scripts/m06_web_fixtures.py`, `build_fixture_project`) is built afresh and served by
`web.create_web_app` — the server the shell talks to — through Starlette's `TestClient`. Every
request the screens of §6 make on that project (the keys of `tests/web/fixtures/w26/
exchanges.json`, which `scripts/m06_web_fixtures.py` captured through `dispatch`) is sent as
`js/api.js` sends it (`buildRequest`: path parameters percent-encoded as one segment each, a GET's
other members as query text, a POST's as a JSON body), as the principal that asked it, together
with the requests the fixtures cannot hold because they act on live state (`wait_job`,
`cancel_job`, a fresh `submit_job`). Each answer is held to the contract:

- the status the fixture recorded for the same request (a refusal stays a refusal, with its
  code), and an `ApiError` document at its code's HTTP status for every refusal;
- a 200 document satisfies its operation's response schema;
- a raw export's bytes are the bytes its bundle listing registers (SHA-256 and size, and the
  `X-Content-SHA256` header) and satisfy the record schema of their kind.

One test per operation: 17 of 17, each with at least one successful answer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote, urlencode

import pytest
from conftest import REPO_ROOT
from test_m06_fixtures_valid import KIND_SCHEMA, NO_RECORD_SCHEMA, _check_record
from test_m06_static_scan import UI_OPERATIONS

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.types import ApiError, schema_errors, validate_inline

if TYPE_CHECKING:
    from starlette.testclient import TestClient

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)

EXCHANGES: Final[Path] = REPO_ROOT / "tests" / "web" / "fixtures" / "w26" / "exchanges.json"
#: Who asked the fixtures' caller-independent requests (`scripts/m06_web_fixtures.py`).
SHARED_PRINCIPAL: Final[str] = "agent-a"

_spec = importlib.util.spec_from_file_location(
    "m06_web_fixtures", REPO_ROOT / "scripts" / "m06_web_fixtures.py"
)
assert _spec is not None and _spec.loader is not None
fixtures = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("m06_web_fixtures", fixtures)
_spec.loader.exec_module(fixtures)


@cache
def _exchanges() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(EXCHANGES.read_text("utf-8"))
    return document


@cache
def _requests() -> dict[str, list[tuple[str, dict[str, Any], int | None]]]:
    """`{operation: [(principal, members, recorded status or None)]}`: every request the
    fixtures recorded, and the ones they cannot hold (`None`: no recorded status; must be 200)."""
    found: dict[str, list[tuple[str, dict[str, Any], int | None]]] = {}

    def add(principal: str, key: str, status: int | None) -> None:
        name, _, members = key.partition(" ")
        found.setdefault(name, []).append((principal, json.loads(members), status))

    for key, record in _exchanges()["shared"].items():
        add(SHARED_PRINCIPAL, key, record["status"])
    for principal, records in _exchanges()["principals"].items():
        for key, record in records.items():
            add(principal, key, record["status"])
    # Live state: a wait on an ended job answers at once; a cancel of an ended job returns it as
    # it is (§4.2); a fresh solve under the Solve dialog's key shape (inline: it ends at once).
    # Each independent of the others' order. A running job's wait and cancel are the browser
    # test's (`test_m06_browser_smoke.py`).
    fresh = {
        "operation": "solve",
        "idempotency_key": "ui-solve-" + "0" * 32,
        "body": {"revision_id": "rev-000002", "policy_id": "default"},
    }
    for name, members in (
        ("wait_job", {"job_id": "job-000001", "after_sequence": -1, "timeout_s": 1}),
        ("wait_job", {"job_id": "job-000003", "after_sequence": 0, "timeout_s": 1}),
        ("cancel_job", {"job_id": "job-000001"}),
        ("cancel_job", {"job_id": "job-000003"}),
        ("submit_job", fresh),
    ):
        found.setdefault(name, []).append(("agent-a", members, None))
    return found


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Any, TestClient]]:
    # The skip lives here, not at module level, so the tests are collected (and skipped) without
    # the server extra: T08.A22 resolves its evidence references by collection (M06 review F2c).
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from openflowsheet.application.bindings import web

    project = fixtures.build_fixture_project(tmp_path_factory.mktemp("m06-g2") / "project")
    owner = LocalApplication.open(project.path)
    with TestClient(web.create_web_app(owner), raise_server_exceptions=False) as served:
        yield project, served
    owner.close()


def _js_string(value: Any) -> str:
    """JavaScript's `String(value)` for the scalars a query carries."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def over_http(served: TestClient, token: str, name: str, members: dict[str, Any]) -> Any:
    """One request as `js/api.js` `buildRequest` sends it."""
    http = OPERATIONS[name].http
    assert http is not None, name
    verb, path = http
    rest = dict(members)
    for member in list(rest):
        marker = "{" + member + "}"
        if marker in path:
            path = path.replace(marker, quote(_js_string(rest.pop(member)), safe=""))
    assert "{" not in path, (name, path)
    headers = {"Authorization": f"Bearer {token}"}
    if verb == "GET":
        query = urlencode({key: _js_string(value) for key, value in rest.items()})
        return served.get(f"{path}?{query}" if query else path, headers=headers)
    headers["Content-Type"] = "application/json"
    body = json.dumps(rest, separators=(",", ":"), ensure_ascii=False).encode()
    return served.post(path, content=body, headers=headers)


def _listed(served: TestClient, token: str, artifact_id: str) -> dict[str, Any]:
    """The bundle listing's row of member `artifact_id`, read over HTTP."""
    bundle = artifact_id.split("/", 1)[0]
    response = over_http(
        served,
        token,
        "get_artifact",
        {"artifact_id": bundle, "depth": 12, "limit": 200, "pointer": ""},
    )
    assert response.status_code == 200
    (member,) = (m for m in response.json()["value"]["files"] if m["artifact_id"] == artifact_id)
    return dict(member)


def _check_raw(served: TestClient, token: str, artifact_id: str, response: Any) -> None:
    data = response.content
    member = _listed(served, token, artifact_id)
    digest = hashlib.sha256(data).hexdigest()
    assert (digest, len(data)) == (member["sha256"], member["size_bytes"]), artifact_id
    assert response.headers["X-Content-SHA256"] == digest
    document = json.loads(data)
    kind = member["kind"]
    if kind == "solve_trace":
        assert isinstance(document, list) and document
        for event in document:
            _check_record("solve-event.schema.json", event)
    elif kind in KIND_SCHEMA:
        _check_record(KIND_SCHEMA[kind], document)
    else:
        assert kind in NO_RECORD_SCHEMA and isinstance(document, dict), kind


def test_the_requests_cover_exactly_the_seventeen() -> None:
    assert set(_requests()) == UI_OPERATIONS


@pytest.mark.parametrize("name", sorted(UI_OPERATIONS))
def test_g2_every_ui_operation_answers_schema_valid_over_http(
    client: tuple[Any, TestClient], name: str
) -> None:
    project, served = client
    operation = OPERATIONS[name]
    succeeded = 0
    for principal, members, recorded in _requests()[name]:
        validate_inline(name, operation.request_schema, members)
        token = project.tokens[principal]
        response = over_http(served, token, name, members)
        where = (principal, name, members)
        assert response.status_code == (recorded or 200), (where, response.text[:400])
        if response.status_code != 200:
            document = response.json()
            assert schema_errors("api-error.schema.json", document) == [], where
            assert ApiError.from_document(document).http_status == response.status_code, where
            continue
        succeeded += 1
        if operation.response_schema is None:
            _check_raw(served, token, members["artifact_id"], response)
        else:
            validate_inline(name, operation.response_schema, response.json())
    assert succeeded > 0, name
