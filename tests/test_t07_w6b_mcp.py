"""T07 W6b: the MCP binding, through a real stdio session (design note §11.3, §10.2, §10.6, §11.6).

The server is spawned as a subprocess the way a client starts it (`serving.serve_mcp`, token from
`OPENFLOWSHEET_TOKEN_FILE`), and driven by the SDK's own `ClientSession` over `stdio_client`,
which also validates every successful result against the tool's `outputSchema` with an empty
schema registry — so every success here also proves that schema self-contained (§11.3, R4).

- **G14, the MCP half** (§11.6): `list_tools` is `OPERATIONS`' MCP rows one to one, with the
  inlined request and response schemas; every MCP-exposed operation, called over stdio, equals
  `dispatch` called directly on the same project as the same principal — reads exactly, effects
  against the direct replay of the same request, refusals error document for error document; the
  import-graph lint of `bindings/`.
- **G15, the served half**: the description each tool is served with hashes to `REVIEW.json`
  and is at most 1500 characters (the file half is `test_t07_w6c_descriptions.py`).
- **§10.2**: a missing, unreadable, unknown or revoked credential refuses the start (non-zero
  exit, nothing served); a capability revoked while the server runs is refused
  `unauthenticated` on its next call; a missing right is `forbidden`, as in-process.

The stdio tests skip cleanly without the `server` extra; the lint runs everywhere.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator
from t07_corpus import CORPUS
from t07_mcp_support import (
    CAPABILITY,
    PRINCIPAL,
    SERVER,
    SESSION_TIMEOUT_S,
    Outcome,
    Session,
    call,
    direct_call,
    environment,
    in_session,
    project_with_grant,
)

from openflowsheet.application.authz import revoke
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.types import (
    DocumentSchemaError,
    validate_inline,
)

NOMINAL = "SYN-001-nominal"
BINDINGS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings"
DESCRIPTIONS = BINDINGS / "descriptions"
#: §4.3's MCP rows, tool name → operation, in the table's order.
MCP_ROWS: dict[str, str] = {
    op.mcp_tool: name
    for name, op in OPERATIONS.items()
    if "mcp" in op.transports and op.mcp_tool is not None
}


# ======================================================================= import-graph lint

#: §11.6 (2): what a module under `bindings/` may import. `anyio` is the SDK's own event loop
#: library, which §11.3 names for running calls off it.
ALLOWED_PROJECT_MODULES = {
    f"openflowsheet.application.{name}"
    for name in ("contract", "types", "operations", "projection")
}
ALLOWED_THIRD_PARTY = {"mcp", "anyio", "starlette", "uvicorn"}
#: M06 §5.2: the web shell's server builds on the HTTP binding and reads the packaged files
#: through `openflowsheet.resources` (standard library only).
ALLOWED_PER_MODULE = {
    "web.py": {"openflowsheet.application.bindings.http", "openflowsheet.resources"},
}


def _imports(path: Path) -> set[str]:
    """Every module `path` imports, at any depth of its body, relative imports resolved."""
    package = "openflowsheet.application.bindings"
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                module = f"{base}.{node.module}" if node.module else base
            else:
                assert node.module is not None
                module = node.module
            found.add(module)
            if module.split(".")[0] == "openflowsheet":
                # `from openflowsheet.application import local` imports a module too.
                found.update(
                    f"{module}.{alias.name}"
                    for alias in node.names
                    if _is_module(f"{module}.{alias.name}")
                )
    return found


def _is_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # `name` is an attribute of a module, not a submodule
        return False


def _allowed(module: str, extra: frozenset[str] = frozenset()) -> bool:
    top = module.split(".")[0]
    if top == "openflowsheet":
        return module in ALLOWED_PROJECT_MODULES or module in extra
    return top in ALLOWED_THIRD_PARTY or top in sys.stdlib_module_names or top == "__future__"


@pytest.mark.parametrize("path", sorted(BINDINGS.glob("*.py")), ids=lambda p: p.name)
def test_g14_the_bindings_import_only_the_contract(path: Path) -> None:
    """§11.6 (2): nothing under `orchestrator`, `verify`, `models`, `run`, `numerics` or `thermo`,
    and of the application only the contract — never `local`, `authz` or the store, so a binding
    cannot reach past `dispatch`. The composition root is `serving`, outside `bindings/`."""
    imported = _imports(path)
    extra = frozenset(ALLOWED_PER_MODULE.get(path.name, ()))
    refused = sorted(module for module in imported if not _allowed(module, extra))
    assert refused == [], f"{path.name} imports outside §11.6 (2): {refused}"
    if path.name == "mcp.py":
        assert "openflowsheet.application.operations" in imported


def test_the_lint_refuses_what_it_should(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import numpy\n"
        "from openflowsheet.application import local\n"
        "from openflowsheet.application.authz import grant\n"
        "from ..store import ProjectStore\n"
        "def f():\n    from openflowsheet.run import replay\n",
        encoding="utf-8",
    )
    assert sorted(m for m in _imports(probe) if not _allowed(m)) == [
        "numpy",
        "openflowsheet.application",
        "openflowsheet.application.authz",
        "openflowsheet.application.local",
        "openflowsheet.application.store",
        "openflowsheet.run",
        "openflowsheet.run.replay",
    ]


def test_the_serving_module_imports_no_server_library() -> None:
    """The CLI can import the composition root without the extra; `mcp` loads only on start."""
    probe = (
        "import sys\n"
        "import openflowsheet.application.serving\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in {'mcp', 'starlette', "
        "'uvicorn'}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
        env=environment(None),
        timeout=120,
    )
    assert result.stdout.strip() == "[]"


def _timeless(document: Any) -> Any:
    """A validation report's `provenance.timestamp` is the one clock reading in these reads."""
    if isinstance(document, dict):
        return {k: _timeless(v) for k, v in document.items() if k != "timestamp"}
    if isinstance(document, list):
        return [_timeless(item) for item in document]
    return document


# ============================================================= the conformance transcript


@dataclass
class Pair:
    """One request, over MCP and directly. `relation` says how the two must agree."""

    label: str
    operation: str
    request: dict[str, Any]
    mcp: Outcome
    direct: Outcome
    relation: str = "equal"  # "equal", "timeless", "replay" (direct replays the MCP effect)


@dataclass
class Transcript:
    tools: list[Any] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    refused_tools: dict[str, Outcome] = field(default_factory=dict)
    submitted: dict[str, Any] = field(default_factory=dict)
    streamed_events: list[dict[str, Any]] = field(default_factory=list)
    audit: list[dict[str, Any]] = field(default_factory=list)
    wall_s: float = 0.0
    server_log: str = ""


async def _scenario(session: Session, direct: LocalApplication, record: Transcript) -> None:
    record.tools = (await session.list_tools()).tools

    async def pair(label: str, name: str, request: dict[str, Any], relation: str = "equal") -> Any:
        tool = OPERATIONS[name].mcp_tool
        assert tool is not None
        via_mcp = await call(session, tool, request)
        via_direct = direct_call(direct, name, request)
        record.pairs.append(Pair(label, name, request, via_mcp, via_direct, relation))
        return via_mcp[1]

    await pair("project", "get_project", {})
    await pair("models", "list_models", {})
    document = CORPUS[NOMINAL]()
    first = {
        "edits": [{"operation": "set", "path": [k], "value": v} for k, v in document.items()],
        "expected_revision": None,
        "idempotency_key": "w6b-first",
    }
    revision = (await pair("commit first", "commit_change", first, "replay"))["revision_id"]
    title = {
        "edits": [{"operation": "set", "path": ["title"], "value": "W6b"}],
        "expected_revision": revision,
    }
    await pair("preview", "preview_change", title, "timeless")
    second = (
        await pair("commit second", "commit_change", title | {"idempotency_key": "w6b-2"}, "replay")
    )["revision_id"]
    await pair("validate", "validate", {"revision_id": second, "task": "simulation"}, "timeless")
    page = await pair("revisions page 1", "list_revisions", {"limit": 1})
    await pair("revisions page 2", "list_revisions", {"limit": 1, "cursor": page["next_cursor"]})
    await pair(
        "revision view",
        "get_revision",
        {"revision_id": revision, "pointer": "/connections", "limit": 2},
    )
    await pair("diff", "diff_revisions", {"from_revision": revision, "to_revision": second})
    await pair("structure", "inspect_structure", {"revision_id": second, "depth": 2})

    solve = {"operation": "solve", "idempotency_key": "w6b-solve", "body": {"revision_id": second}}
    error, submitted = await call(session, "submit_job", solve)
    assert not error, submitted
    record.submitted = submitted
    job_id = submitted["job"]["job_id"]
    after = -1
    while True:
        error, waited = await call(
            session, "wait_job", {"job_id": job_id, "after_sequence": after, "timeout_s": 30}
        )
        assert not error, waited
        record.streamed_events.extend(waited["events"])
        if waited["events"]:
            after = waited["events"][-1]["sequence"]
        if waited["ended"]:
            break
    await pair("submit replayed", "submit_job", solve)
    outputs = (await pair("job", "get_job", {"job_id": job_id}))["outputs"]
    await pair("result", "get_job_result", {"job_id": job_id})
    await pair("wait ended", "wait_job", {"job_id": job_id, "timeout_s": 0})
    await pair("cancel ended", "cancel_job", {"job_id": job_id})
    await pair("jobs", "list_jobs", {"limit": 1})
    events = await pair("events page 1", "list_job_events", {"job_id": job_id, "limit": 3})
    await pair(
        "events page 2",
        "list_job_events",
        {"job_id": job_id, "after_sequence": int(events["next_cursor"]), "limit": 3},
    )
    await pair("events all", "list_job_events", {"job_id": job_id, "limit": 500})
    (bundle,) = [output["artifact_id"] for output in outputs if output["kind"] == "replay_bundle"]
    files = (await pair("bundle", "get_artifact", {"artifact_id": bundle}))["value"]["files"]
    (state,) = [f["artifact_id"] for f in files if f["name"] == "solution-state.json"]
    await pair(
        "state",
        "get_artifact",
        {"artifact_id": state, "pointer": "/variable_ids", "limit": 5},
    )

    # Refusals: each is the same error document over MCP as in-process.
    await pair("not found", "get_job", {"job_id": "job-999999"})
    await pair("no revision", "validate", {"revision_id": "absent", "task": "simulation"})
    await pair("bad pointer", "get_artifact", {"artifact_id": state, "pointer": "/nowhere"})
    await pair("schema", "list_jobs", {"limit": 0})
    await pair("reserved key", "submit_job", solve | {"idempotency_key": "auto:mine"})
    await pair("key reused", "commit_change", first | {"expected_revision": second})
    big = {**first, "idempotency_key": "w6b-big", "expected_revision": second}
    big["edits"] = [{"operation": "set", "path": ["title"], "value": 2**53 + 1}]
    await pair("non-canonical", "commit_change", big)

    for tool in ("solve", "reproduce", "artifact_bytes", "validate", "no_such_tool"):
        record.refused_tools[tool] = await call(session, tool, {})


@pytest.fixture(scope="module")
def transcript(tmp_path_factory: pytest.TempPathFactory) -> Transcript:
    pytest.importorskip("mcp")
    root = tmp_path_factory.mktemp("w6b")
    capability, token_file = project_with_grant(root / "project", ("draft", "execute", "read"))
    record = Transcript()
    direct = LocalApplication.open(root / "project", capability=capability)
    try:
        started = time.monotonic()
        in_session(
            root / "project",
            token_file,
            root / "server.log",
            lambda session: _scenario(session, direct, record),
        )
        record.wall_s = time.monotonic() - started
        record.audit = direct.store.audit_rows()
        record.server_log = (root / "server.log").read_text(encoding="utf-8")
    finally:
        direct.close()
    print(f"\nW6b stdio conformance session: {record.wall_s:.1f} s wall")
    return record


# ================================================================================== G14


def test_g14_list_tools_is_the_mcp_rows_one_to_one(transcript: Transcript) -> None:
    from openflowsheet.application.bindings.mcp import input_schema, self_contained

    listed = [tool.name for tool in transcript.tools]
    assert listed == list(MCP_ROWS)  # the table's order, each once
    assert set(listed).isdisjoint({"solve", "reproduce", "artifact_bytes"})
    for tool in transcript.tools:
        operation = OPERATIONS[MCP_ROWS[tool.name]]
        assert tool.inputSchema == input_schema(operation)
        if tool.name != "submit_job":  # the one request schema with a top-level combinator
            assert tool.inputSchema == self_contained(operation.request_schema)
        assert operation.response_schema is not None
        assert tool.outputSchema == self_contained(operation.response_schema, consumer=True)
        assert "$ref" not in json.dumps(tool.inputSchema) + json.dumps(tool.outputSchema)
        assert tool.inputSchema["type"] == tool.outputSchema["type"] == "object"


def test_g14_the_inlined_request_schema_decides_as_the_table_does(transcript: Transcript) -> None:
    """Every request of the transcript, valid or not, is accepted by the served `inputSchema`
    (resolved with an empty registry, as a client would) iff the table's schema accepts it. (The
    served `submit_job` schema does not tie a body to its operation, W6e; the transcript sends
    no such pair — `test_submit_job_is_served_without_a_top_level_combinator` does.)"""
    from referencing import Registry

    served = {MCP_ROWS[tool.name]: tool.inputSchema for tool in transcript.tools}
    for pair in transcript.pairs:
        validator = Draft202012Validator(served[pair.operation], registry=Registry())
        try:
            validate_inline(pair.operation, OPERATIONS[pair.operation].request_schema, pair.request)
            table = True
        except DocumentSchemaError:
            table = False
        assert validator.is_valid(pair.request) == table, pair.label


def test_g14_every_mcp_operation_equals_dispatch_as_the_same_principal(
    transcript: Transcript,
) -> None:
    assert {pair.operation for pair in transcript.pairs} == set(MCP_ROWS.values())
    for pair in transcript.pairs:
        (mcp_error, via_mcp), (direct_error, via_direct) = pair.mcp, pair.direct
        assert mcp_error == direct_error, pair.label
        if pair.relation == "equal":
            assert via_mcp == via_direct, pair.label
        elif pair.relation == "timeless":
            assert _timeless(via_mcp) == _timeless(via_direct), pair.label
        else:  # the direct call replays the effect the MCP call made
            assert via_mcp["status"] == "committed" and via_direct["status"] == "replayed"
            assert via_mcp | {"status": "replayed"} == via_direct, pair.label


def test_g14_a_submitted_job_is_the_job_the_store_holds(transcript: Transcript) -> None:
    """The first submit's response (the job as it was accepted) against the ended job: every
    member fixed at acceptance agrees; the stream MCP followed is the job's whole event list."""
    submitted = transcript.submitted
    assert submitted["replayed"] is False
    ended = next(p for p in transcript.pairs if p.label == "job").direct[1]
    fixed = (
        "job_id",
        "operation",
        "request",
        "request_sha256",
        "principal_id",
        "capability_id",
        "policy_sha256",
        "effective_budgets",
        "created_at",
    )
    assert {k: submitted["job"][k] for k in fixed} == {k: ended[k] for k in fixed}
    assert ended["principal_id"] == PRINCIPAL and ended["status"] == "completed"
    everything = next(p for p in transcript.pairs if p.label == "events all").direct[1]["items"]
    assert transcript.streamed_events == everything


def test_the_session_ran_a_real_verified_solve_and_the_server_logged_no_error(
    transcript: Transcript,
) -> None:
    """The transcript is not vacuous: the solve ran in a process worker to a VERIFIED
    certificate, and the server wrote no traceback or refusal to its log (its stderr)."""
    result = next(p for p in transcript.pairs if p.label == "result").mcp[1]
    run = result["run_result"]
    assert (run["outcome"], run["verification_status"]) == ("CONVERGED", "VERIFIED")
    kinds = [output["kind"] for output in run["outputs"]]
    assert kinds[:3] == ["solution_certificate", "run_manifest", "replay_bundle"]
    assert "Traceback" not in transcript.server_log
    assert "refused" not in transcript.server_log


def test_g14_refusals_reach_mcp_as_tool_errors_with_the_api_error(transcript: Transcript) -> None:
    codes = {pair.label: pair.mcp[1]["code"] for pair in transcript.pairs if pair.mcp[0] is True}
    assert codes == {
        "not found": "not_found",
        "no revision": "not_found",
        "bad pointer": "not_found",
        "schema": "invalid_request",
        "reserved key": "invalid_request",
        "key reused": "idempotency_key_reused",
        "non-canonical": "document_not_canonical",
    }


def test_the_tools_mcp_does_not_expose_are_refused_and_audited(transcript: Transcript) -> None:
    for tool, (error, document) in transcript.refused_tools.items():
        assert error is True, tool
        assert document["code"] == "invalid_request"
        assert document["detail"]["tool"] == tool
        assert document["detail"]["tools"] == sorted(MCP_ROWS)
    audited = [
        row["operation"]
        for row in transcript.audit
        if row["code"] == "invalid_request" and row["operation"] in transcript.refused_tools
    ]
    assert sorted(audited) == sorted(transcript.refused_tools)


def test_every_effect_is_the_session_principals(transcript: Transcript) -> None:
    # The operator's `project init` and `project grant` rows come first; then the session's own.
    effects = [
        row
        for row in transcript.audit
        if row["effect"] is not None and not row["operation"].startswith("project_")
    ]
    # The cancel of the ended job, over MCP and directly, changes nothing and is audited all the
    # same (ruling round 5, S10).
    assert [row["operation"] for row in effects] == [
        "commit_change",
        "commit_change",
        "submit_job",
        "cancel_job",
        "cancel_job",
    ]
    assert {(row["principal_id"], row["capability_id"]) for row in effects} == {
        (PRINCIPAL, CAPABILITY)
    }


# ================================================================================== G15


def test_g15_the_served_descriptions_are_the_reviewed_texts(transcript: Transcript) -> None:
    review = json.loads((DESCRIPTIONS / "REVIEW.json").read_text(encoding="utf-8"))
    for tool in transcript.tools:
        name = MCP_ROWS[tool.name]
        served = tool.description
        assert (
            hashlib.sha256(served.encode("utf-8")).hexdigest()
            == (review["operations"][name]["sha256"])
        ), name
        assert len(served) <= 1500


# ============================================================================ credentials


def _refusal(project: Path, token_file: Path | None) -> str:
    """`serve_mcp`'s refusal to start, in-process (it returns before touching stdio)."""
    from openflowsheet.application.serving import SERVE_REFUSED, serve_mcp

    stderr = io.StringIO()
    assert serve_mcp(project, token_file, stderr=stderr) == SERVE_REFUSED
    return stderr.getvalue()


def test_a_bad_credential_refuses_the_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§10.2: no anonymous server. Refusing the start (rather than refusing every call) is the
    safer reading: no tool is ever listed to a client without a valid credential."""
    pytest.importorskip("mcp")
    monkeypatch.delenv("OPENFLOWSHEET_TOKEN_FILE", raising=False)
    capability, token_file = project_with_grant(tmp_path / "project", ("read",))
    token = token_file.read_text(encoding="utf-8").strip()
    project = tmp_path / "project"
    assert "no credential" in _refusal(project, None)
    assert "cannot be read" in _refusal(project, tmp_path / "absent.token")
    forged = tmp_path / "forged.token"
    forged.write_text("prt_" + "A" * 43, encoding="utf-8")
    assert "matches no current grant" in _refusal(project, forged)
    malformed = tmp_path / "malformed.token"
    malformed.write_text("GRANT policy", encoding="utf-8")
    assert "matches no current grant" in _refusal(project, malformed)
    revoke(project, capability.capability_id)
    message = _refusal(project, token_file)
    assert "matches no current grant" in message and token not in message


def test_a_bad_credential_exits_non_zero_before_serving(tmp_path: Path) -> None:
    """The same end to end: the spawned server exits non-zero and writes nothing to stdout."""
    pytest.importorskip("mcp")
    _, token_file = project_with_grant(tmp_path / "project", ("read",))
    forged = tmp_path / "forged.token"
    forged.write_text("prt_" + "B" * 43, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", SERVER, str(tmp_path / "project")],
        input="",
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=environment(forged),
        timeout=SESSION_TIMEOUT_S,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "refused to start" in result.stderr


def test_a_revoked_capability_is_refused_on_its_next_call(tmp_path: Path) -> None:
    """§10.2: re-authorized on every call against the current policy. Also: a right the grant
    lacks is `forbidden` over MCP exactly as in-process."""
    pytest.importorskip("mcp")
    project = tmp_path / "project"
    capability, token_file = project_with_grant(project, ("read",))
    direct = LocalApplication.open(project, capability=capability)
    commit = {
        "edits": [{"operation": "set", "path": ["title"], "value": "x"}],
        "expected_revision": None,
        "idempotency_key": "w6b-forbidden",
    }

    async def body(session: Session) -> list[Outcome]:
        outcomes = [
            await call(session, "get_project", {}),
            await call(session, "commit_change", commit),
        ]
        revoke(project, capability.capability_id)
        outcomes.append(await call(session, "get_project", {}))
        outcomes.append(await call(session, "list_revisions", {}))
        return outcomes

    try:
        forbidden_direct = direct_call(direct, "commit_change", commit)
        allowed, forbidden, *revoked = in_session(project, token_file, tmp_path / "log", body)
    finally:
        direct.close()
    assert allowed[0] is False and allowed[1]["principal_id"] == PRINCIPAL
    assert forbidden == forbidden_direct and forbidden[1]["code"] == "forbidden"
    for error, document in revoked:
        assert error is True and document["code"] == "unauthenticated"


# ============================================================ W6e: no top-level combinator


def test_no_tool_input_schema_has_a_top_level_combinator() -> None:
    """Clients (the Claude API among them) refuse a tool `input_schema` whose top level is
    `oneOf`, `anyOf` or `allOf`; `not` and `if` go with them (W6e)."""
    pytest.importorskip("mcp")
    from openflowsheet.application.bindings.mcp import TOP_LEVEL_COMBINATORS, tools

    assert set(TOP_LEVEL_COMBINATORS) == {"oneOf", "anyOf", "allOf", "not", "if"}
    served = {tool.name: tool.inputSchema for tool in tools()}
    assert list(served) == list(MCP_ROWS)
    for name, schema in served.items():
        assert set(schema).isdisjoint(TOP_LEVEL_COMBINATORS), name
        assert schema["type"] == "object", name


def test_submit_job_is_served_without_a_top_level_combinator(tmp_path: Path) -> None:
    """J3's branches are served as `body.oneOf`: the served schema admits each branch's body and
    no longer ties it to the operation. `dispatch` still does, so a solve body under `reproduce`
    (and a reproduce body under `solve`) is refused `invalid_request` over MCP, as in-process,
    and creates no job."""
    pytest.importorskip("mcp")
    from referencing import Registry
    from t07_mcp_support import in_memory

    from openflowsheet.application.bindings.mcp import input_schema, self_contained

    row = OPERATIONS["submit_job"]
    table = self_contained(row.request_schema)
    served = input_schema(row)
    assert "oneOf" in table and "oneOf" not in served
    assert served["properties"]["body"]["oneOf"] == [
        branch["properties"]["body"] for branch in table["oneOf"]
    ]
    assert {k: v for k, v in served.items() if k != "properties"} == {
        k: v for k, v in table.items() if k not in ("properties", "oneOf")
    }
    solve_body = {"revision_id": "r-1"}
    reproduce_body = {"bundle_artifact_id": "job-000001:bundle", "rerun": False}
    crossed = [
        {"operation": "reproduce", "idempotency_key": "w6e-a", "body": solve_body},
        {"operation": "solve", "idempotency_key": "w6e-b", "body": reproduce_body},
    ]
    matched = [
        {"operation": "solve", "idempotency_key": "w6e-c", "body": solve_body},
        {"operation": "reproduce", "idempotency_key": "w6e-d", "body": reproduce_body},
    ]
    client = Draft202012Validator(served, registry=Registry())
    for request in [*crossed, *matched]:
        assert client.is_valid(request), request
    for request in crossed:
        with pytest.raises(DocumentSchemaError):
            validate_inline("submit_job", row.request_schema, request)
    unknown = {"operation": "solve", "idempotency_key": "w6e-e", "body": {"revision": "r-1"}}
    assert not client.is_valid(unknown)

    project = tmp_path / "project"
    capability, _ = project_with_grant(project, ("draft", "execute", "read"))
    with LocalApplication.open(project, capability=capability) as app:

        async def body(session: Session) -> list[Outcome]:
            return [await call(session, "submit_job", request) for request in crossed]

        over_mcp = in_memory(app, body)
        for request, outcome in zip(crossed, over_mcp, strict=True):
            assert outcome == direct_call(app, "submit_job", request)
            error, document = outcome
            assert error is True and document["code"] == "invalid_request", document
        assert app.store.job_ids() == ()
