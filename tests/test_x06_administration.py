"""X06-WO4: in-band policy administration (ADR 0078 D5). Exit tests E-X06-16 to E-X06-21
(E-X06-22, the served digest, is `tests/test_t08_w2_surface_digest.py`'s and
`tests/test_m07a_surface_chain.py`'s; the four operations on all six clients are
`tests/test_t07_conformance.py`'s `_administration`):

- **E-X06-16** the switch off (the default): each write `unsupported administration_disabled`, the
  policy file's bytes unchanged, one `refused` audit row; the policy files the operator commands
  write (the repository commits none, as X04's A11 found) keep their bytes and `policy_sha256`;
- **E-X06-17** the delegation rule: a case table through the service, each refusal with its code,
  and 1000 generated (caller, request) pairs through `authz.delegation_refusal`;
- **E-X06-18** a granted token authenticates on the next REST, MCP-over-HTTP and MCP-stdio call; a
  replay returns `token: null`; neither the token nor any `prt_` string is in `project.sqlite3`, its
  WAL, the policy file or the captured logs;
- **E-X06-19** an owner marked `serving_remote` (as `serve_http` marks it beyond loopback) refuses
  each write `unsupported administration_remote_refused` and serves the reads; on loopback the
  writes succeed;
- **E-X06-20** an in-band revoke takes effect on the revoked token's next call; 10 concurrent
  in-band grants plus one CLI grant all end in the policy file;
- **E-X06-21** each in-band write leaves exactly one `allowed` audit row naming the caller and the
  effect; the operator CLI's audit rows equal their pre-WO4 form (`tests/fixtures/x06/
  pre_wo4_cli_audit.json`, taken at `4ca7ce3c`).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_transport_support import dispatched
from x06_schema_support import ADMINISTERED_CAPABILITY, administration_requests

from openflowsheet.application.authz import (
    DELEGATED_LIMITS,
    delegation_refusal,
    grant,
    read_policy,
    set_administration,
)
from openflowsheet.application.cli import main
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.policy_types import (
    LOCAL_OWNER_PRINCIPAL,
    RIGHTS,
    CapabilityReference,
    Limits,
)
from openflowsheet.application.serving import token_capability
from openflowsheet.application.store import DATABASE_NAME, POLICY_NAME
from openflowsheet.application.store_records import policy_file_bytes
from openflowsheet.canonical import document_sha256

SERVER_EXTRA = all(
    importlib.util.find_spec(name) is not None for name in ("mcp", "starlette", "httpx", "uvicorn")
)
if SERVER_EXTRA:
    import anyio
    import httpx

    from openflowsheet.application.serving import http_application, serve_http

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)
needs_server = pytest.mark.skipif(not SERVER_EXTRA, reason="needs the server extra")

PROJECT_ID = "x06-administration"
ADMIN, ADMIN_CAPABILITY = "x06-admin", "cap-x06-admin"
ADMIN_RIGHTS = ("draft", "execute", "policy", "read")
NO_LIMITS = Limits()
HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
WRITES = ("grant_capability", "revoke_capability", "set_ambient_pressure")
#: ADR 0078 D5.5: a write's `effect`, as the operator CLI's.
EFFECTS = {
    "grant_capability": f"grant:{ADMINISTERED_CAPABILITY}",
    "revoke_capability": f"revoke:{ADMINISTERED_CAPABILITY}",
    "set_ambient_pressure": "ambient:100000.0",
}


def make_project(
    root: Path,
    *,
    switch: bool = True,
    rights: tuple[str, ...] = ADMIN_RIGHTS,
    limits: Limits = NO_LIMITS,
    expires_at: str | None = None,
) -> tuple[Path, CapabilityReference, str]:
    """A project with one operator grant holding `policy` (the administrator), and the switch."""
    directory = root / "project"
    LocalApplication.create(directory, project_id=PROJECT_ID).close()
    admin, token = grant(
        directory,
        principal_id=ADMIN,
        rights=rights,
        limits=limits,
        expires_at=expires_at,
        capability_id=ADMIN_CAPABILITY,
    )
    if switch:
        set_administration(directory, True)
    return directory, admin, token


def audit(directory: Path) -> list[dict[str, Any]]:
    with LocalApplication.open(directory) as owner:
        return owner.store.audit_rows()


def detail_code(document: dict[str, Any]) -> str:
    return str(document["detail"]["code"])


def a_grant(capability_id: str, key: str, **members: Any) -> dict[str, Any]:
    """A `read` grant within every limited caller below, unless `members` say otherwise (a
    member given as `None` is left out)."""
    request = {
        "principal_id": f"agent-{capability_id}",
        "rights": ["read"],
        "limits": {"default_wall_time_s": 60, "max_wall_time_s": 60, "max_active_jobs": 1},
        "expires_at": "2030-01-01T00:00:00.000000Z",
        "capability_id": capability_id,
        "idempotency_key": key,
        **members,
    }
    return {name: value for name, value in request.items() if value is not None}


# ============================================================================ E-X06-16


@pytest.mark.parametrize("as_owner", [False, True], ids=["grant holding policy", "local owner"])
def test_e_x06_16_switch_off_each_write_is_refused_and_changes_nothing(
    tmp_path: Path, as_owner: bool
) -> None:
    directory, admin, _ = make_project(tmp_path, switch=False)
    policy_file = directory / POLICY_NAME
    before = policy_file.read_bytes()
    assert "administration" not in json.loads(before)
    caller = None if as_owner else admin
    principal = LOCAL_OWNER_PRINCIPAL if as_owner else ADMIN
    with LocalApplication.open(directory, capability=caller) as owner:
        for name, request in administration_requests():
            error, document = dispatched(owner, name, request)
            if name == "get_policy":  # the read is served (D5.3 refuses the writes)
                assert not error and document == read_policy(policy_file).as_document()
                continue
            assert error and document["code"] == "unsupported", (name, document)
            assert detail_code(document) == "administration_disabled"
            assert policy_file.read_bytes() == before, name
    rows = [row for row in audit(directory) if row["operation"] in WRITES]
    assert sorted(row["operation"] for row in rows) == sorted(WRITES)
    for row in rows:
        assert (row["outcome"], row["code"], row["principal_id"]) == (
            "refused",
            "unsupported",
            principal,
        )


def test_e_x06_16_the_policy_files_keep_their_bytes_and_hash(tmp_path: Path) -> None:
    """The repository commits no `project-policy.json` (X04's A11): the policies the operator
    commands write are the existing ones. Each parses and re-serializes to its bytes and its
    `policy_sha256`; none gains `administration`; switching on adds that member alone, and off
    restores the bytes."""
    directory = tmp_path / "project"
    LocalApplication.create(directory, project_id=PROJECT_ID).close()
    policy_file = directory / POLICY_NAME
    steps: list[Callable[[], object]] = [
        lambda: None,
        lambda: grant(directory, principal_id="agent-1", capability_id="cap-1"),
        lambda: grant(
            directory,
            principal_id="agent-2",
            rights=("read",),
            expires_at="2030-01-01T00:00:00.000000Z",
            note="a label",
            capability_id="cap-2",
        ),
        lambda: main(
            ["project", "ambient", "--project", str(directory), "--pressure", "1"]
            + ["--unit", "bar"]
        ),
    ]
    for step in steps:
        step()
        data = policy_file.read_bytes()
        document = json.loads(data)
        assert "administration" not in document
        policy = read_policy(policy_file)
        assert policy_file_bytes(policy) == data
        assert policy.policy_sha256 == document_sha256(document)
        assert policy.as_document() == document
        assert set_administration(directory, True) is True
        switched = json.loads(policy_file.read_bytes())
        assert switched == {**document, "administration": {"in_band": True}}
        assert set_administration(directory, False) is False
        assert policy_file.read_bytes() == data


def test_e_x06_16_a_written_false_is_refused(tmp_path: Path) -> None:
    """DECISION WO4-1: off is absence only, one document per policy."""
    directory, _, _ = make_project(tmp_path, switch=False)
    document = json.loads((directory / POLICY_NAME).read_bytes())
    (directory / POLICY_NAME).write_text(
        json.dumps({**document, "administration": {"in_band": False}}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        read_policy(directory / POLICY_NAME)


# ============================================================================ E-X06-17

#: The limited, expiring administrator of the case table.
LIMITED = Limits(default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=4)
EXPIRY = "2031-01-01T00:00:00.000000Z"
#: (label, request, expected code, expected detail code)
CASES: list[tuple[str, dict[str, Any], str | None, str | None]] = [
    ("within the caller", a_grant("cap-ok", "k0"), None, None),
    (
        "a right beyond",
        a_grant("cap-r", "k1", rights=["draft", "read"]),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "a missing limit",
        a_grant(
            "cap-m",
            "k2",
            limits={"default_wall_time_s": 60, "max_wall_time_s": None, "max_active_jobs": 1},
        ),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "a larger wall time",
        a_grant(
            "cap-w",
            "k3",
            limits={"default_wall_time_s": 60, "max_wall_time_s": 3600, "max_active_jobs": 1},
        ),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "more active jobs",
        a_grant(
            "cap-j",
            "k4",
            limits={"default_wall_time_s": 60, "max_wall_time_s": 60, "max_active_jobs": 5},
        ),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "a later expiry",
        a_grant("cap-e", "k5", expires_at="2032-01-01T00:00:00.000000Z"),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "no expiry",
        {k: v for k, v in a_grant("cap-n", "k6").items() if k != "expires_at"},
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "the local owner's principal",
        a_grant("cap-o", "k7", principal_id=LOCAL_OWNER_PRINCIPAL),
        "forbidden",
        "grant_exceeds_caller",
    ),
    (
        "the local owner's id",
        a_grant(LOCAL_OWNER_PRINCIPAL, "k8"),
        "forbidden",
        "grant_exceeds_caller",
    ),
    ("an existing id", a_grant("cap-ok", "k9"), "invalid_request", "capability_exists"),
]


def test_e_x06_17_the_case_table(tmp_path: Path) -> None:
    directory, admin, _ = make_project(
        tmp_path, rights=("execute", "policy", "read"), limits=LIMITED, expires_at=EXPIRY
    )
    # A more privileged grant (`draft`, which the administrator lacks), made by the operator.
    grant(directory, principal_id="agent-drafter", rights=("draft", "read"), capability_id="cap-d")
    policy_file = directory / POLICY_NAME
    with LocalApplication.open(directory, capability=admin) as owner:
        for label, request, code, detail in CASES:
            before = policy_file.read_bytes()
            error, document = dispatched(owner, "grant_capability", request)
            if code is None:
                assert not error and document["status"] == "granted", (label, document)
                continue
            assert error, (label, document)
            assert (document["code"], detail_code(document)) == (code, detail), label
            assert policy_file.read_bytes() == before, label
        error, document = dispatched(
            owner, "revoke_capability", {"capability_id": "cap-d", "idempotency_key": "r1"}
        )
        assert error and (document["code"], detail_code(document)) == (
            "forbidden",
            "revoke_exceeds_caller",
        )
        error, document = dispatched(
            owner, "revoke_capability", {"capability_id": "cap-absent", "idempotency_key": "r2"}
        )
        assert error and (document["code"], detail_code(document)) == (
            "not_found",
            "capability_not_found",
        )
        # Revoking oneself is allowed (D5.3).
        error, document = dispatched(
            owner,
            "revoke_capability",
            {"capability_id": ADMIN_CAPABILITY, "idempotency_key": "r3"},
        )
        assert not error and document["status"] == "revoked", document
    ids = [c["capability_id"] for c in json.loads(policy_file.read_bytes())["capabilities"]]
    assert sorted(ids) == ["cap-d", "cap-ok"]


def _capability(
    rng: random.Random, name: str, near: CapabilityReference | None = None
) -> CapabilityReference:
    """A random capability; `near` a caller, each part is often taken from it (its rights a
    subset of the caller's), so that both outcomes are frequent."""

    def pick(own: Any, choices: list[Any]) -> Any:
        return own if near is not None and rng.random() < 0.6 else rng.choice(choices)

    pool = near.rights if near is not None and rng.random() < 0.8 else RIGHTS
    rights = tuple(sorted(r for r in pool if rng.random() < 0.5))
    limits = near.limits if near is not None else Limits()
    wall = pick(limits.max_wall_time_s, [None, 60.0, 600.0, 1800.0, 3600.0])
    jobs = pick(limits.max_active_jobs, [None, 1, 2, 4, 8])
    expiry = pick(
        near.expires_at if near is not None else None,
        [None, "2029-01-01T00:00:00.000000Z", "2030-06-01T00:00:00.000000Z"],
    )
    principal = LOCAL_OWNER_PRINCIPAL if rng.random() < 0.02 else f"agent-{name}"
    return CapabilityReference(
        capability_id=f"cap-{name}",
        principal_id=principal,
        rights=rights,  # type: ignore[arg-type]
        token_sha256=None,
        limits=Limits(default_wall_time_s=None, max_wall_time_s=wall, max_active_jobs=jobs),
        expires_at=expiry,
        note="",
    )


def test_e_x06_17_a_thousand_generated_pairs() -> None:
    """Granted if and only if the rights are a subset, each delegated caller limit is met by a
    non-null limit at most it, a caller expiry by a non-null expiry at most it, and neither id
    is the local owner's."""
    rng = random.Random(20261127)
    granted = refused = 0
    for index in range(1000):
        caller = _capability(rng, f"c{index}")
        requested = _capability(rng, f"r{index}", caller)
        allowed = (
            LOCAL_OWNER_PRINCIPAL not in (requested.principal_id, requested.capability_id)
            and set(requested.rights) <= set(caller.rights)
            and all(
                getattr(caller.limits, name) is None
                or (
                    getattr(requested.limits, name) is not None
                    and getattr(requested.limits, name) <= getattr(caller.limits, name)
                )
                for name in DELEGATED_LIMITS
            )
            and (
                caller.expires_at is None
                or (requested.expires_at is not None and requested.expires_at <= caller.expires_at)
            )
        )
        reason = delegation_refusal(caller, requested)
        assert (reason is None) == allowed, (caller, requested, reason)
        granted += reason is None
        refused += reason is not None
    assert granted >= 200 and refused >= 200, (granted, refused)


# ============================================================================ the server


def served[T](
    directory: Path, body: Callable[[httpx.AsyncClient], Awaitable[T]], *, remote: bool = False
) -> T:
    """`serving.http_application` over an owner of `directory` (REST and `/mcp`), its lifespan
    running; `remote` marks the owner as `serve_http` marks one bound beyond loopback."""
    owner = LocalApplication.open(directory)
    owner.serving_remote = remote

    async def run() -> T:
        application = http_application(owner, host=HOST, port=PORT)
        async with (
            application.router.lifespan_context(application),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url=BASE, timeout=60
            ) as client,
        ):
            with anyio.fail_after(120):
                return await body(client)

    try:
        return anyio.run(run)
    finally:
        owner.close()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def rest(
    client: httpx.AsyncClient, token: str, verb: str, path: str, body: Any = None
) -> httpx.Response:
    if verb == "GET":
        return await client.get(path, headers=bearer(token))
    return await client.post(
        path,
        content=json.dumps(body),
        headers={**bearer(token), "Content-Type": "application/json"},
    )


async def mcp_call(
    client: httpx.AsyncClient, token: str, tool: str, arguments: dict[str, Any]
) -> httpx.Response:
    message = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    return await client.post(
        "/mcp", content=json.dumps(message), headers={**headers, **bearer(token)}
    )


# ============================================================================ E-X06-18


@needs_server
def test_e_x06_18_the_token_is_shown_once_and_written_nowhere(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    directory, _, admin_token = make_project(tmp_path)
    request = a_grant("cap-new", "g1", rights=["read"], expires_at=None)
    seen: dict[str, Any] = {}

    async def body(client: httpx.AsyncClient) -> None:
        granted = await rest(client, admin_token, "POST", "/v1/policy/grants", request)
        assert granted.status_code == 200, granted.text
        seen["granted"] = granted.json()
        token = seen["granted"]["token"]
        replay = await rest(client, admin_token, "POST", "/v1/policy/grants", request)
        seen["replay"] = replay.json()
        # The next REST call and the next MCP-over-HTTP call act as the new grant.
        project = await rest(client, token, "GET", "/v1/project")
        assert project.status_code == 200, project.text
        called = await mcp_call(client, token, "get_project", {})
        assert called.status_code == 200 and called.json()["result"]["isError"] is False
        assert called.json()["result"]["structuredContent"] == project.json()
        # The store's bytes while the owner holds them (the WAL not yet checkpointed).
        seen["live"] = b"".join(
            path.read_bytes() for path in sorted(directory.glob(f"{DATABASE_NAME}*"))
        )

    served(directory, body)
    token = seen["granted"]["token"]
    assert token.startswith("prt_") and len(token) == 47
    assert (seen["replay"]["status"], seen["replay"]["token"]) == ("replayed", None)
    assert seen["replay"]["capability"] == seen["granted"]["capability"]
    # The next MCP stdio call: `serve-mcp` resolves its token file to this capability.
    token_file = tmp_path / "token"
    token_file.write_text(token + "\n", encoding="utf-8")
    capability = token_capability(directory, token_file)
    assert capability.capability_id == "cap-new"
    with LocalApplication.open(directory, capability=capability) as owner:
        assert stdio_call(owner, "get_project")["isError"] is False
    # Nowhere: the store (and its WAL), the policy file, the captured logs and output.
    stored = b"".join(path.read_bytes() for path in sorted(directory.glob(f"{DATABASE_NAME}*")))
    out, err = capfd.readouterr()
    for name, data in (
        ("store (live)", seen["live"]),
        ("store", stored),
        ("policy", (directory / POLICY_NAME).read_bytes()),
        ("logs", caplog.text.encode("utf-8")),
        ("output", (out + err).encode("utf-8")),
    ):
        assert token.encode() not in data, name
        assert token.removeprefix("prt_").encode() not in data, name
        assert b"prt_" not in data, name
    assert caplog.records  # something was logged at DEBUG


def stdio_call(owner: LocalApplication, tool: str) -> dict[str, Any]:
    """One `tools/call` through the SDK's in-memory session into `build_server`, the server
    `serve-mcp` runs over stdio, acting as `owner`."""
    from mcp.shared.memory import create_connected_server_and_client_session

    from openflowsheet.application.bindings.mcp import build_server

    async def run() -> dict[str, Any]:
        async with create_connected_server_and_client_session(
            build_server(lambda: owner), raise_exceptions=True
        ) as session:
            result = await session.call_tool(tool, {})
            return {"isError": result.isError, "structured": result.structuredContent}

    return anyio.run(run)


# ============================================================================ E-X06-19


@needs_server
@pytest.mark.parametrize("remote", [True, False], ids=["beyond loopback", "loopback"])
def test_e_x06_19_a_remote_server_refuses_the_writes_and_serves_the_reads(
    tmp_path: Path, remote: bool
) -> None:
    directory, _, token = make_project(tmp_path)
    before = (directory / POLICY_NAME).read_bytes()

    async def body(client: httpx.AsyncClient) -> list[tuple[str, int, Any]]:
        out = []
        for name, request in administration_requests():
            verb, route = OPERATIONS[name].http  # type: ignore[misc]
            path = route.format(**request)
            members = {k: v for k, v in request.items() if f"{{{k}}}" not in route}
            response = await rest(client, token, verb, path, members)
            out.append((name, response.status_code, response.json()))
        return out

    answers = served(directory, body, remote=remote)
    for name, status, document in answers:
        if name == "get_policy" or not remote:
            assert status == 200, (name, document)
            continue
        assert document["code"] == "unsupported", (name, document)
        assert detail_code(document) == "administration_remote_refused"
    if remote:
        assert (directory / POLICY_NAME).read_bytes() == before
        refused = [r for r in audit(directory) if r["operation"] in WRITES]
        assert [r["outcome"] for r in refused] == ["refused"] * 3
    else:
        assert [a[2]["status"] for a in answers[1:]] == ["set", "granted", "revoked"]


@needs_server
@pytest.mark.parametrize(("host", "remote"), [("0.0.0.0", True), ("127.0.0.1", False)])
def test_e_x06_19_serve_http_marks_the_owner_from_its_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host: str, remote: bool
) -> None:
    from openflowsheet.application.bindings import http

    directory, _, _ = make_project(tmp_path)
    ran: list[bool] = []
    owner = LocalApplication.open(directory)
    monkeypatch.setattr(http, "run", lambda *args, **kwargs: ran.append(owner.serving_remote))
    try:
        assert owner.serving_remote is False
        serve_http(owner, host=host, port=PORT, allow_remote=True)
    finally:
        owner.close()
    assert ran == [remote]


# ============================================================================ E-X06-20


@needs_server
def test_e_x06_20_an_in_band_revoke_takes_effect_on_the_next_call(tmp_path: Path) -> None:
    directory, _, admin_token = make_project(tmp_path)

    async def body(client: httpx.AsyncClient) -> tuple[int, int, int, int]:
        request = a_grant("cap-short", "g1", expires_at=None)
        token = (await rest(client, admin_token, "POST", "/v1/policy/grants", request)).json()[
            "token"
        ]
        before = (await rest(client, token, "GET", "/v1/project")).status_code
        before_mcp = (await mcp_call(client, token, "get_project", {})).status_code
        revoked = await rest(
            client,
            admin_token,
            "POST",
            "/v1/policy/grants/cap-short/revoke",
            {"idempotency_key": "r1"},
        )
        assert revoked.json()["status"] == "revoked", revoked.text
        after = await rest(client, token, "GET", "/v1/project")
        after_mcp = await mcp_call(client, token, "get_project", {})
        assert after.json()["code"] == "unauthenticated"
        return before, before_mcp, after.status_code, after_mcp.status_code

    assert served(directory, body) == (200, 200, 401, 401)


@needs_server
def test_e_x06_20_concurrent_grants_lose_no_update(tmp_path: Path) -> None:
    """Ten in-band grants at once (the REST binding runs each in its own worker thread) and one
    operator CLI grant beside them: all eleven end in the policy file."""
    directory, _, admin_token = make_project(tmp_path)

    async def body(client: httpx.AsyncClient) -> list[int]:
        statuses: list[int] = []

        async def one(index: int) -> None:
            request = a_grant(f"cap-{index:02d}", f"g{index}", expires_at=None)
            response = await rest(client, admin_token, "POST", "/v1/policy/grants", request)
            statuses.append(response.status_code)

        def operator() -> None:
            arguments = ["project", "grant", "--project", str(directory)]
            arguments += ["--principal", "agent-cli", "--capability-id", "cap-cli"]
            assert main(arguments) == 0

        async with anyio.create_task_group() as group:
            group.start_soon(anyio.to_thread.run_sync, operator)
            for index in range(10):
                group.start_soon(one, index)
        return statuses

    assert served(directory, body) == [200] * 10
    ids = {
        c["capability_id"]
        for c in json.loads((directory / POLICY_NAME).read_bytes())["capabilities"]
    }
    assert ids == {ADMIN_CAPABILITY, "cap-cli", *(f"cap-{i:02d}" for i in range(10))}
    grants = [
        r for r in audit(directory) if r["operation"] in ("grant_capability", "project_grant")
    ]
    assert sorted(r["effect"] for r in grants if r["outcome"] == "allowed") == sorted(
        [f"grant:{ADMIN_CAPABILITY}", "grant:cap-cli", *(f"grant:cap-{i:02d}" for i in range(10))]
    )


# ============================================================================ E-X06-21


def test_e_x06_21_each_in_band_write_leaves_one_allowed_row(tmp_path: Path) -> None:
    directory, admin, _ = make_project(tmp_path)
    requests = dict(administration_requests())
    with LocalApplication.open(directory, capability=admin) as owner:
        for name, request in administration_requests():
            if name == "get_policy":
                continue
            for _ in range(2):  # the second is a replay, which writes nothing
                error, document = dispatched(owner, name, request)
                assert not error, document
        error, document = dispatched(
            owner, "set_ambient_pressure", {"value": None, "idempotency_key": "ad4"}
        )
        assert not error, document
    rows = [r for r in audit(directory) if r["operation"] in WRITES]
    assert all(r["outcome"] == "allowed" for r in rows)
    expected = [
        ("set_ambient_pressure", EFFECTS["set_ambient_pressure"]),
        ("grant_capability", EFFECTS["grant_capability"]),
        ("revoke_capability", EFFECTS["revoke_capability"]),
        ("set_ambient_pressure", "ambient:cleared"),
    ]
    assert [(r["operation"], r["effect"]) for r in rows] == expected
    for row in rows:
        assert (row["principal_id"], row["capability_id"]) == (ADMIN, ADMIN_CAPABILITY)
    for row, name in zip(
        rows[:3], ("set_ambient_pressure", "grant_capability", "revoke_capability"), strict=True
    ):
        present = {k: v for k, v in requests[name].items() if v is not None}
        assert row["request_sha256"] == document_sha256(present), name


def test_e_x06_21_the_operator_cli_rows_keep_their_form(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator CLI's project init, grant, ambient set and clear, and revoke: their audit
    rows equal those taken at `4ca7ce3c`, before X06-WO4, with `at` removed and each
    `request_sha256` the policy's hash after the step the fixture names."""
    fixture = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "x06" / "pre_wo4_cli_audit.json").read_text("utf-8")
    )
    directory = tmp_path / "project"
    project = ["--project", str(directory)]
    steps = [
        ["project", "init", str(directory), "--project-id", "cli-audit"],
        ["project", "grant", *project, "--principal", "agent-a", "--capability-id", "cap-a"],
        ["project", "ambient", *project, "--pressure", "1", "--unit", "bar"],
        ["project", "ambient", *project, "--clear"],
        ["project", "revoke", *project, "--capability", "cap-a"],
    ]
    hashes = []
    for arguments in steps:
        assert main(arguments) == 0, arguments
        hashes.append(read_policy(directory / POLICY_NAME).policy_sha256)
    capsys.readouterr()
    rows = audit(directory)
    assert len(rows) == len(fixture["rows"])
    for row, expected in zip(rows, fixture["rows"], strict=True):
        after = expected["request_sha256_is_the_policy_hash_after"]
        want = {k: v for k, v in expected.items() if k != "request_sha256_is_the_policy_hash_after"}
        got = {k: v for k, v in row.items() if k not in ("at", "request_sha256")}
        assert got == want
        assert row["request_sha256"] == hashes[after], row
