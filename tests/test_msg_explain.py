"""MSG WO-7: the `explain` operation (design note `docs/design/MSG-messages.md` §3.5, §3.7, §4.9;
ADR 0058 D7).

- for every catalogue key, `explain` returns a schema-valid `message_entry`, equal across Python
  (dispatched), the CLI, HTTP and MCP, and equal to `messages.render.entry_document`;
- an unknown code is refused `not_found` with `{code, suggestions}`: `phase_regim_mismatch` →
  `suggestions[0] == "phase_regime_mismatch"`, one document on every transport, the refusal audited;
- the suggestions are the keys within edit distance 3, case-insensitively, at most 5, sorted by
  (distance, key), checked against an independent distance;
- the top-level CLI `explain <code> [--json]` needs no project and exits 0 and 6 (§3.7).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
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
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import MessageEntry, schema_errors
from openflowsheet.messages.catalogue import CATALOGUE, FORMAT_ID
from openflowsheet.messages.render import entry_document, suggestions
from openflowsheet.messages.text import STUB_NOTE, format_entry

ENTRY = "application-results.schema.json#/$defs/message_entry"
TYPO = "phase_regim_mismatch"
REFERENCE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*(![a-z]+)?\}")


# ======================================================================= the entry document


def test_the_row_is_a_read_on_all_four_transports() -> None:
    row = OPERATIONS["explain"]
    assert row.right == "read"
    assert row.http == ("GET", "/v1/explain/{code}")
    assert row.mcp_tool == "explain"
    assert row.transports == ("python", "cli", "http", "mcp")
    assert row.description_file == "descriptions/explain.md"
    assert row.response_schema == {
        "$ref": "https://github.com/frankp/process-runtime/schemas/"
        "application-results.schema.json#/$defs/message_entry"
    }


def test_every_entry_document_is_schema_valid_and_round_trips() -> None:
    digest = CATALOGUE.sha256()
    for code in CATALOGUE.keys():
        document = entry_document(code)
        assert document is not None
        assert schema_errors(ENTRY, document) == [], code
        assert MessageEntry.from_document(document).as_document() == document
        assert document["code"] == code
        assert document["catalogue"] == {"id": FORMAT_ID, "sha256": digest}
        assert document["docs"].endswith(f"/#{code}")
        # §4.9: display forms — no param reference survives (`[[`/`]]` literals may).
        for name in ("summary", "context", "where", "why", "action"):
            text = document[name]
            assert text is None or REFERENCE.search(text) is None, (code, name, text)


def test_a_worked_entry_shows_its_display_templates_and_rendered_examples() -> None:
    document = entry_document("phase_regime_mismatch")
    assert document is not None
    assert document["summary"] == (
        "Stream <stream> is not in its declared phase: it is declared <declared>, but at these "
        "conditions it is <landed>."
    )
    assert [param["name"] for param in document["params"]][:2] == ["stream", "unit"]
    assert document["params"][0] == {
        "name": "stream",
        "type": "stream",
        "label": "stream",
        "optional": False,
    }
    (example,) = document["examples"]
    assert example["code"] == "phase_regime_mismatch"
    assert example["chain"] == [
        "INITIALIZATION_FAILED",
        "initializer_failed",
        "phase_regime_mismatch",
    ]
    assert "'S4'" in example["cause"]


def test_an_unknown_code_has_no_entry() -> None:
    assert entry_document(TYPO) is None
    assert entry_document("") is None


# ======================================================================= suggestions (§3.5)


def _reference_distance(a: str, b: str) -> int:
    """Levenshtein distance by its recursive definition (independent of the engine's table)."""

    @cache
    def d(i: int, j: int) -> int:
        if i == 0 or j == 0:
            return i + j
        return min(d(i - 1, j) + 1, d(i, j - 1) + 1, d(i - 1, j - 1) + (a[i - 1] != b[j - 1]))

    return d(len(a), len(b))


@pytest.mark.parametrize(
    "code", [TYPO, "NOT_FOUND", "not_fund", "unsupportd", "CONVERGED", "convergd", "xyzzy", "L-TH-"]
)
def test_suggestions_are_the_near_keys_case_insensitively_by_distance_then_key(code: str) -> None:
    near = sorted(
        (distance, key)
        for key in CATALOGUE.keys()
        if (distance := _reference_distance(code.lower(), key.lower())) <= 3
    )
    assert suggestions(code) == [key for _, key in near[:5]]


def test_the_typo_suggests_the_intended_code_first() -> None:
    assert suggestions(TYPO)[0] == "phase_regime_mismatch"
    assert suggestions("NOT_FOUND")[0] == "not_found"
    assert suggestions("xyzzy-nothing-like-it") == []


# ======================================================================= Python, as a method


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any, str]:
    directory = tmp_path_factory.mktemp("msg-explain") / "project"
    LocalApplication.create(directory, project_id="msg-explain").close()
    capability, token = grant(directory, principal_id="agent-explain", rights=("read",))
    return directory, capability, token


def test_the_method_returns_the_entry_and_refuses_an_unknown_code_audited(
    project: tuple[Path, Any, str],
) -> None:
    directory, capability, _ = project
    with LocalApplication.open(directory, capability=capability) as app:
        entry = app.explain("not_found")
        assert isinstance(entry, MessageEntry)
        assert entry.as_document() == entry_document("not_found")
        with pytest.raises(ApplicationError) as refused:
            app.explain(TYPO)
        error = refused.value.error
        assert error.code == "not_found"
        assert error.detail == {"code": TYPO, "suggestions": suggestions(TYPO)}
        assert error.explanation["summary"] == f"There is no message code '{TYPO}'."
        assert error.explanation["action"] == "Did you mean phase_regime_mismatch?"
        rows = app.list_audit(principal_id="agent-explain", operation="explain").items
    assert [(row.outcome, row.code) for row in rows] == [("refused", "not_found")]


def test_no_close_code_reads_the_plain_action(project: tuple[Path, Any, str]) -> None:
    directory, _, _ = project
    with LocalApplication.open(directory) as app, pytest.raises(ApplicationError) as refused:
        app.explain("xyzzy-nothing-like-it")
    error = refused.value.error
    assert error.detail == {"code": "xyzzy-nothing-like-it", "suggestions": []}
    assert error.explanation["action"] == (
        "Check the code's spelling against the docs' Messages section; no message code is close "
        "to it."
    )


@pytest.mark.parametrize("code", ["", "-leading", "has space", "x" * 129, 7])
def test_dispatch_refuses_a_malformed_code_by_the_request_schema(
    project: tuple[Path, Any, str], code: Any
) -> None:
    directory, _, _ = project
    with LocalApplication.open(directory) as app, pytest.raises(ApplicationError) as refused:
        dispatch(app, "explain", {"code": code})
    assert refused.value.error.code == "invalid_request"


# ======================================================================= the four transports


@pytest.fixture
def clients(project: tuple[Path, Any, str], tmp_path: Path) -> Iterator[dict[str, Client]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    directory, capability, token = project
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    made: dict[str, Client] = {
        "python": PythonInline(directory),
        "cli": CliClient(directory, tmp_path / "raw.bin", out, err),
        "http": HttpClient(directory, token),
        "mcp": McpClient(directory, capability),
    }
    try:
        yield made
    finally:
        for client in made.values():
            client.close()


def _thread_streams(clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch) -> None:
    client = clients["cli"]
    assert isinstance(client, CliClient)
    monkeypatch.setattr(sys, "stdout", client.out)
    monkeypatch.setattr(sys, "stderr", client.err)


def test_every_key_is_one_schema_valid_document_on_the_four_transports(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    _thread_streams(clients, monkeypatch)
    for code in CATALOGUE.keys():
        expected = entry_document(code)
        for name, client in clients.items():
            is_error, document = client.call("explain", {"code": code})
            assert not is_error, (name, code, document)
            assert document == expected, (name, code)
        assert schema_errors(ENTRY, expected) == [], code


def test_an_unknown_code_is_one_refusal_on_the_four_transports(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    _thread_streams(clients, monkeypatch)
    documents = {}
    for name, client in clients.items():
        is_error, document = client.call("explain", {"code": TYPO})
        assert is_error, name
        documents[name] = document
    first = documents["python"]
    assert all(document == first for document in documents.values()), documents
    assert first["code"] == "not_found"
    assert first["detail"]["code"] == TYPO
    assert first["detail"]["suggestions"][0] == "phase_regime_mismatch"
    assert first["detail"]["explanation"]["action"] == "Did you mean phase_regime_mismatch?"


# ======================================================================= the top-level CLI (§3.7)


def test_the_cli_explains_a_code_without_a_project(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["explain", "phase_regime_mismatch"]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    document = entry_document("phase_regime_mismatch")
    assert document is not None
    assert out == format_entry(document) + "\n"
    lines = out.split("\n")
    assert lines[0] == "phase_regime_mismatch: Declared phase does not match the computed state"
    assert f"  Summary: {document['summary']}" in lines
    assert f"  Docs:    {document['docs']}" in lines
    assert "Example:" in lines


def test_the_cli_json_is_the_entry_document(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["explain", "not_found", "--json"]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert json.loads(out) == entry_document("not_found")


def test_a_stub_says_it_is_one(capsys: pytest.CaptureFixture[str]) -> None:
    stub = next(entry.code for entry in CATALOGUE.entries() if not entry.complete)
    assert cli.main(["explain", stub]) == 0
    assert f"  Note:    {STUB_NOTE}" in capsys.readouterr().out.split("\n")


def test_the_cli_refuses_an_unknown_code_with_exit_6(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["explain", TYPO]) == cli.API_EXIT_CODES["not_found"] == 6
    out, err = capsys.readouterr()
    assert out == ""
    lines = err.split("\n")
    assert lines[0] == f"There is no message code '{TYPO}'."
    assert "  Do:      Did you mean phase_regime_mismatch?" in lines
    assert err.endswith("  Details: not_found: no such message code\n")
    assert cli.main(["explain", TYPO, "--json"]) == 6
    out, err = capsys.readouterr()
    document = json.loads(out)
    assert document["code"] == "not_found"
    assert document["detail"]["suggestions"][0] == "phase_regime_mismatch"
    assert document["detail"]["explanation"]["summary"] == err.split("\n")[0]
