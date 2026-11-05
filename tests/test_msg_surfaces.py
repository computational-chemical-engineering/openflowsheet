"""MSG WO-3: `ApiError` explanations on every surface, and FB-03(b)'s useful `not_found`
(design note `docs/design/MSG-messages.md` §3.3, §3.4, §3.7, §4.5, §4.7, §4.13.3).

- the schema walk of §4.7: the locations where a response schema `$ref`s `api-error.schema.json`,
  and an error placed at each one is projected with `detail.explanation`;
- `project_error` attaches the explanation before bounding, idempotently; a direct call's
  document is unchanged, and `str(ApplicationError)` is the layered text ending in the old string;
- FB-03(b): reading `solution-state.json` from a run that did not converge is refused
  `not_found` with the bundle's members and the run's outcome, equal across the four transports;
- an injected defect on HTTP, MCP and the CLI gives `internal_error` with a `bug`-kind
  explanation;
- no handler turns an `ApplicationError` into text by `str()` (§4.7's rule, statically).
"""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application import cli
from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError, api_error
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import (
    ANY,
    OPERATIONS,
    _error_refs,
    error_locations,
    project_error,
    project_response,
)
from openflowsheet.application.projection import TEXT_LIMIT
from openflowsheet.application.types import ApiError, Change, published_schemas, schema_errors
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.messages.render import RenderContext, render_error

# ============================================================== §4.7: the schema walk

#: Every location of an `ApiError` in a response, read off the schemas by hand (`job.error`,
#: `run_result.error`, `transaction_result.error`, `job_event.error`).
EXPECTED_LOCATIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "commit_change": (("error",),),
    "solve": (("error",),),
    "submit_job": (("job", "error"),),
    "get_job": (("error",),),
    "list_jobs": (("items", ANY, "error"),),
    "list_job_events": (("items", ANY, "error"),),
    "wait_job": (("events", ANY, "error"), ("job", "error")),
    "cancel_job": (("error",),),
    "get_job_result": (("error",), ("run_result", "error")),
    "preview_change": (("error",),),
}

ERROR = ApiError(
    code="not_found", message="no such job", retryable=False, detail={"job_id": "job-000007"}
)


def test_the_error_locations_are_the_response_schemas_api_error_refs() -> None:
    found = {name: error_locations(name) for name in OPERATIONS if error_locations(name)}
    assert found == EXPECTED_LOCATIONS


def test_the_walk_follows_combinators_items_and_maps() -> None:
    reference = {"$ref": "https://github.com/frankp/process-runtime/schemas/api-error.schema.json"}
    schema = {
        "properties": {
            "a": {"anyOf": [reference, {"type": "null"}]},
            "b": {"type": "array", "items": {"properties": {"e": reference}}},
            "c": {"additionalProperties": reference},
            "d": {"prefixItems": [{"allOf": [reference]}]},
            "f": {"type": "string"},
        }
    }
    found: set[tuple[str, ...]] = set()
    _error_refs(schema, published_schemas(), None, (), (), found)
    assert found == {("a",), ("b", ANY, "e"), ("c", ANY), ("d", ANY)}


def _skeleton(location: tuple[str, ...], error: dict[str, Any]) -> Any:
    if not location:
        return error
    step, rest = location[0], location[1:]
    inner = _skeleton(rest, error)
    return [inner, inner] if step == ANY else {step: inner, "other": "kept"}


def _at(document: Any, location: tuple[str, ...]) -> list[Any]:
    if not location:
        return [document]
    step, rest = location[0], location[1:]
    if step == ANY:
        return [found for item in document for found in _at(item, rest)]
    return _at(document[step], rest)


@pytest.mark.parametrize(
    ("name", "location"),
    [(name, location) for name, locations in EXPECTED_LOCATIONS.items() for location in locations],
)
def test_an_error_at_each_location_is_projected_with_its_explanation(
    name: str, location: tuple[str, ...]
) -> None:
    document = _skeleton(location, ERROR.as_document())
    before = json.dumps(document, sort_keys=True)
    projected = project_response(OPERATIONS[name], document)
    assert json.dumps(document, sort_keys=True) == before  # nothing the caller holds moved
    for error in _at(projected, location):
        assert error["detail"]["explanation"] == render_error(ERROR.as_document())
        assert error["detail"]["job_id"] == "job-000007"
        assert schema_errors("api-error.schema.json", error) == []
    assert projected == project_response(OPERATIONS[name], projected)  # idempotent


def test_a_response_without_an_error_is_only_bounded() -> None:
    document = {"error": None, "other": "kept"}
    assert project_response(OPERATIONS["get_job"], document) == document


# ======================================================= project_error and the Python surface


def test_project_error_attaches_before_bounding_and_is_idempotent() -> None:
    long = ApiError(
        code="invalid_request",
        message="x" * (TEXT_LIMIT + 50),
        retryable=False,
        detail={"pointer": "/a"},
    )
    projected = project_error(long)
    explanation = projected.detail["explanation"]
    assert explanation["code"] == "invalid_request"
    assert explanation["kind"] == "input"
    assert len(projected.message) == TEXT_LIMIT
    assert all(len(text) <= TEXT_LIMIT for text in _strings(explanation))
    assert project_error(projected) == projected
    assert schema_errors("api-error.schema.json", projected.as_document()) == []


def _strings(document: Any) -> Iterator[str]:
    if isinstance(document, str):
        yield document
    elif isinstance(document, dict):
        for value in document.values():
            yield from _strings(value)
    elif isinstance(document, list):
        for item in document:
            yield from _strings(item)


def test_a_direct_call_keeps_its_document_and_str_is_the_layered_text() -> None:
    refused = api_error("not_found", "no such revision", revision_id="rev-000009")
    assert refused.error.as_document() == {
        "code": "not_found",
        "message": "no such revision",
        "detail": {"revision_id": "rev-000009"},
        "retryable": False,
    }
    assert refused.args == ("not_found: no such revision",)
    text = str(refused)
    lines = text.split("\n")
    assert lines[0] == refused.explanation["summary"]
    assert lines[0] == "Nothing named 'rev-000009' exists in this project."
    assert lines[-1] == "  Details: not_found: no such revision"
    assert "  Code:    not_found (openflowsheet explain not_found)" in lines
    assert refused.error.explanation == render_error(refused.error.as_document())
    assert "explanation" not in refused.error.detail


# ===================================================================== FB-03(b) on four transports

RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"


def _c01() -> dict[str, Any]:
    """MSG corpus C01: the README Rankine change set with the boiler at 973.15 K."""
    document: dict[str, Any] = json.loads(RANKINE.read_text(encoding="utf-8"))
    for edit in document["edits"]:
        if edit["path"] == ["specifications"]:
            (spec,) = [s for s in edit["value"] if s["id"] == "boiler-T"]
            spec["value"] = 973.15
    return document


class Failed:
    def __init__(self, project: Path, job_id: str, bundle_id: str, token: str, capability: Any):
        self.project, self.job_id, self.bundle_id = project, job_id, bundle_id
        self.token, self.capability = token, capability


@pytest.fixture(scope="module")
def failed(tmp_path_factory: pytest.TempPathFactory) -> Failed:
    project = tmp_path_factory.mktemp("msg-fb03") / "project"
    with LocalApplication.create(project, project_id="msg-fb03") as app:
        change, expected, key = Change.from_change_set(_c01())
        committed = app.commit_change(change, expected, key)
        assert committed.revision_id is not None
        result = app.solve(committed.revision_id, "default")
        assert result.outcome == "INITIALIZATION_FAILED", result.outcome
        bundle = next(o.artifact_id for o in result.outputs if o.kind == "replay_bundle")
        job_id = result.job_id
    capability, token = grant(project, principal_id="agent-msg", rights=("read",))
    return Failed(project, job_id, bundle, token, capability)


def _members(failed: Failed) -> list[str]:
    """The bundle's file names on disk, independent of the store's member query."""
    with LocalApplication.open(failed.project) as app:
        row = app._store.artifact(failed.bundle_id)
        assert row is not None
        directory = app.files_root / row.relpath
    return sorted(path.name for path in directory.rglob("*") if path.is_file())


def test_fb03b_the_refusal_names_the_bundle_its_members_and_the_run_outcome(
    failed: Failed,
) -> None:
    missing = f"{failed.bundle_id}/solution-state.json"
    with LocalApplication.open(failed.project) as app:
        with pytest.raises(ApplicationError) as refused:
            app.artifact_bytes(missing)
    detail = dict(refused.value.error.detail)
    members = detail.pop("members")
    assert detail == {
        "artifact_id": missing,
        "bundle_id": failed.bundle_id,
        "member": "solution-state.json",
        "job_id": failed.job_id,
        "run_outcome": "INITIALIZATION_FAILED",
    }
    assert refused.value.error.message == "no such artifact"  # I1
    assert members == sorted(members) == _members(failed)
    assert "failure-bundle.json" in members and "solution-state.json" not in members
    explanation = refused.value.explanation
    assert explanation["summary"] == (
        f"Bundle '{failed.bundle_id}' has no file 'solution-state.json': its run ended "
        "INITIALIZATION_FAILED and wrote no solution."
    )
    assert explanation["why"] == (
        "A run that does not converge writes a failure bundle instead of a solution state and a "
        f"certificate. This bundle holds {', '.join(members)}."
    )
    assert explanation["action"] == (
        "Check the run's outcome before reading its results; the run result's failure says why "
        f"it failed, and '{failed.bundle_id}/failure-bundle.json' holds the evidence."
    )
    assert {(e["type"], e["id"]) for e in explanation["elements"]} == {
        ("artifact", missing),
        ("bundle", failed.bundle_id),
        ("job", failed.job_id),
    }
    assert str(refused.value).split("\n")[-1] == "  Details: not_found: no such artifact"


def test_fb03b_an_id_that_names_no_bundle_member_keeps_the_old_detail(failed: Failed) -> None:
    with LocalApplication.open(failed.project) as app:
        for missing, call in (
            ("job-999999:bundle/solution-state.json", app.artifact_bytes),
            ("job-999999:nothing", app.get_artifact),
            (f"{failed.bundle_id}/", app.get_artifact),
        ):
            with pytest.raises(ApplicationError) as refused:
                call(missing)
            assert refused.value.error.detail == {"artifact_id": missing}


def test_fb03b_a_member_of_a_converged_run_reads_the_plain_variant(failed: Failed) -> None:
    explanation = render_error(
        {
            "code": "not_found",
            "message": "no such artifact",
            "detail": {
                "artifact_id": "job-000001:bundle/nothing.json",
                "bundle_id": "job-000001:bundle",
                "member": "nothing.json",
                "members": ["run-manifest.json", "solution-state.json"],
                "job_id": "job-000001",
                "run_outcome": "CONVERGED",
            },
        }
    )
    assert explanation["summary"] == "Bundle 'job-000001:bundle' has no file 'nothing.json'."


@pytest.fixture
def clients(failed: Failed, tmp_path: Path) -> Iterator[dict[str, Client]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    made: dict[str, Client] = {
        "python": PythonInline(failed.project),
        "cli": CliClient(failed.project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(failed.project, failed.token),
        "mcp": McpClient(failed.project, failed.capability),
    }
    try:
        yield made
    finally:
        for client in made.values():
            client.close()


def _thread_streams(clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI client's streams as `sys.stdout`/`sys.stderr`, set in the test body: pytest's
    capture resets both between a fixture's setup and the test's call."""
    client = clients["cli"]
    assert isinstance(client, CliClient)
    monkeypatch.setattr(sys, "stdout", client.out)
    monkeypatch.setattr(sys, "stderr", client.err)


def test_fb03b_the_refusal_is_one_document_on_every_transport(
    failed: Failed, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    _thread_streams(clients, monkeypatch)
    missing = f"{failed.bundle_id}/solution-state.json"
    documents: dict[tuple[str, str], Any] = {}
    for name, client in clients.items():
        for operation in ("get_artifact", "artifact_bytes"):
            if operation not in client.carries:
                continue
            is_error, document = client.call(operation, {"artifact_id": missing})
            assert is_error, (name, operation)
            documents[name, operation] = document
    assert set(documents) == {
        ("python", "get_artifact"),
        ("python", "artifact_bytes"),
        ("cli", "get_artifact"),
        ("cli", "artifact_bytes"),
        ("http", "get_artifact"),
        ("http", "artifact_bytes"),
        ("mcp", "get_artifact"),
    }
    for operation in ("get_artifact", "artifact_bytes"):
        same = [document for (_, op), document in documents.items() if op == operation]
        assert all(document == same[0] for document in same[1:]), operation
        explanation = same[0]["detail"]["explanation"]
        assert explanation["code"] == "not_found"
        assert explanation["kind"] == "input"
        assert "INITIALIZATION_FAILED" in explanation["summary"]
        assert explanation["docs"].endswith("/messages/api-errors/#not_found")


def test_fb03b_the_cli_prints_the_document_on_stdout_and_the_text_on_stderr(
    failed: Failed, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = f"{failed.bundle_id}/solution-state.json"
    argv = ["api", "artifact_bytes", "--project", str(failed.project)]
    code = cli.main([*argv, "--json", json.dumps({"artifact_id": missing})])
    out, err = capsys.readouterr()
    assert code == cli.API_EXIT_CODES["not_found"] == 6
    document = json.loads(out)
    assert document["detail"]["explanation"]["summary"] == err.split("\n")[0]
    assert err.endswith("  Details: not_found: no such artifact\n")
    assert "  Kind:    " in err and "  Do:      " in err


# ============================================================== injected defects (§4.7)


def _boom(*_: Any, **__: Any) -> Any:
    raise RuntimeError("an injected defect")


def _assert_internal(document: dict[str, Any]) -> None:
    assert document["code"] == "internal_error"
    explanation = document["detail"]["explanation"]
    assert explanation["code"] == "internal_error"
    assert explanation["kind"] == "bug"
    assert explanation["family"] == "api_error"
    assert schema_errors("api-error.schema.json", document) == []


def test_an_injected_defect_on_http_and_mcp_is_an_explained_internal_error(
    failed: Failed, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(LocalApplication, "get_project", _boom)
    for name in ("http", "mcp"):
        is_error, document = clients[name].call("get_project", {})
        assert is_error, name
        _assert_internal(document)
        assert "an injected defect" not in json.dumps(document)  # §10.4: no traceback text


def test_an_injected_defect_on_the_cli_prints_the_bug_text_then_the_traceback(
    failed: Failed, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(LocalApplication, "get_project", _boom)
    code = cli.main(["api", "get_project", "--project", str(failed.project), "--json", "{}"])
    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    label = CATALOGUE.kind("bug").label
    head, _, rest = err.partition("Traceback (most recent call last):")
    assert head.split("\n")[0] == CATALOGUE.entry("internal_error").document["summary"]
    assert f"  Kind:    {label}\n" in head
    assert "  Code:    internal_error (openflowsheet explain internal_error)\n" in head
    assert "RuntimeError: an injected defect" in rest


# ===================================================== §3.7: validate's explanation lines


def test_validate_adds_a_line_under_a_failing_check_with_a_complete_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    case = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"
    document = yaml.safe_load(case.read_text(encoding="utf-8"))
    del document["provenance"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(document), encoding="utf-8")
    cli.main(["validate", str(broken)])
    plain, _ = capsys.readouterr()
    failing = [
        line.split("] ", 1)[1].split(":", 1)[0]
        for line in plain.split("\n")
        if line.startswith("  [FAIL]") or line.startswith("  [warn]")
    ]
    assert failing, plain
    assert all(not CATALOGUE.entry(check).complete for check in failing)  # stubs: no new line
    entry = CATALOGUE.entry(failing[0])
    monkeypatch.setattr(type(entry), "complete", property(lambda self: True))
    cli.main(["validate", str(broken)])
    explained, _ = capsys.readouterr()
    expected = render_error(
        {"code": failing[0], "message": "", "detail": {}}, context=RenderContext(surface="cli")
    )
    line = f"        {expected['summary']} {expected['action']}"
    assert line in explained.split("\n")
    assert [x for x in explained.split("\n") if not x.startswith("        ")] == [
        x for x in plain.split("\n") if not x.startswith("        ")
    ]


# ============================================================ §4.7: no `str()` conversions

#: The exception classes whose `str()` is layered text after MSG.
LAYERED = {"ApplicationError", "StoreError", "SolveFailedError"}


def _str_conversions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or handler.name is None:
            continue
        names = (
            [handler.type] if not isinstance(handler.type, ast.Tuple) else list(handler.type.elts)
        )
        if not any(isinstance(n, ast.Name) and n.id in LAYERED for n in names):
            continue
        body = ast.Module(body=handler.body, type_ignores=[])
        human = {
            id(inner) for node in ast.walk(body) if _to_stderr(node) for inner in ast.walk(node)
        }
        for node in ast.walk(body):
            if id(node) in human:
                continue
            converted = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("str", "repr")
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == handler.name
            ) or (
                isinstance(node, ast.FormattedValue)
                and isinstance(node.value, ast.Name)
                and node.value.id == handler.name
            )
            if converted:
                found.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    return found


def _to_stderr(node: ast.AST) -> bool:
    """`print(…, file=sys.stderr)`: human text for a human (§3.7), not a document."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        and any(
            keyword.arg == "file"
            and isinstance(keyword.value, ast.Attribute)
            and keyword.value.attr == "stderr"
            for keyword in node.keywords
        )
    )


def test_no_handler_turns_a_layered_error_into_a_document_by_str() -> None:
    sites = [
        site
        for path in sorted((REPO_ROOT / "src" / "openflowsheet").rglob("*.py"))
        for site in _str_conversions(path)
    ]
    assert sites == []


# ================================================================ FB-01 on the command line


def test_fb01_project_init_twice_refuses_with_the_cli_text_and_exist_ok_opens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "plant"
    assert cli.main(["project", "init", str(directory), "--project-id", "p-cli"]) == 0
    created, _ = capsys.readouterr()
    assert cli.main(["project", "init", str(directory), "--project-id", "p-cli"]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    lines = err.split("\n")
    assert lines[0] == (
        f"Directory '{directory}' is not empty: it already holds a project, and project init "
        "needs a new or empty directory."
    )
    assert lines[2] == (
        f"  Do:      The project is ready to use: pass --project {directory} to other commands, "
        "or run project init with --exist-ok."
    )
    assert err.endswith(f"  Details: project_exists: {directory}\n")
    argv = ["project", "init", str(directory), "--project-id", "p-cli", "--exist-ok"]
    assert cli.main(argv) == 0
    opened, err = capsys.readouterr()
    assert (opened, err) == (created, "")
    assert cli.main([*argv[:-3], "--project-id", "p-other", "--exist-ok"]) == 2
    _, err = capsys.readouterr()
    assert err.endswith(f"  Details: project_id_mismatch: {directory}\n")
