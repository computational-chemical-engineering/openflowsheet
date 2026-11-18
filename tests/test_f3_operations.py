"""F3-WO5b (ADR 0061 D13, ADR 0019 Amendment 8): the protocol `Records`, five operations.

- **E-F3-11.** One scenario of the five operations (successes and refusals) returns identical
  canonical documents on Python, the CLI, HTTP and MCP, each over its own fresh project (each
  transport's own promises are checked by its client, `tests/t07_transport_support.py`). Python and
  the CLI act as the local owner (§10.2, §11.5), HTTP and MCP as a grant holding `read`, `draft` and
  `policy`, so the caller's principal id, which a registration and a rights row record, is the one
  member that differs, and only by the caller; the clock members `at` and `date` are left out. The
  CLI conveniences `records search|get|register|validate|rights` print the operations' documents.
  Every code the Records paths emit has a complete catalogue entry. The MCP digest re-take is
  `tests/test_t08_w2_surface_digest.py::test_f3s_surface_move_decomposes_onto_f1s` and link c_10
  of `tests/test_m07a_surface_chain.py`; the R4-G3 snapshots of the existing operations are
  `tests/test_t07_w5e_application_results.py` (`SNAPSHOT_F3` holds only the five new rows).
- **E-F3-5's grant clause** is `tests/test_f3_lock_rights.py`.
- **D11 and the WO4-0 ruling on `register_record`:** a record naming a `legacy.` source is refused
  `reserved_namespace(legacy)` unless its SHA is in the committed legacy index, which copies it
  into the project store; through a user file's `defaults.source_id` as well.
- **D13's `assess_rights` request validation**, item by item.

Expectations are the ADR's: codes, pointers, the D11 row and its `source_sha256` (computed here by
an independent route: SHA-256 of the canonical one-member object, ADR 0002's canonical JSON).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from f3_schema_support import F3_OPERATIONS, user_component, user_record_sha256
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application.authz import grant
from openflowsheet.application.cli import API_EXIT_CODES, main
from openflowsheet.application.errors import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.policy_types import LOCAL_OWNER_PRINCIPAL, Limits
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import CATALOGUE

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import msg_catalogue  # noqa: E402

AGENT = "agent-f3"
SHA = user_record_sha256()
ABSENT = "0" * 64
SECOND = user_component("user.yenonol", "yenonol")
RIGHTS_ROW = {
    "source_id": "user.lab",
    "record_sha256": SHA,
    "scope": "record",
    "assessment": "permitted",
    "basis": "the lab's own measurement",
}
#: E-F3-11's scenario, in order: `(label, operation, request, refused)`.
SCENARIO: tuple[tuple[str, str, dict[str, Any], bool], ...] = (
    ("register", "register_record", {"record": user_component()}, False),
    ("register again", "register_record", {"record": user_component()}, False),
    (
        "register a file",
        "register_record",
        {"file": {"format": "record-v2-json", "content": json.dumps([SECOND])}},
        False,
    ),
    (
        "register a forged source",
        "register_record",
        {"record": user_component("user.zenonol", "zenonol", source="legacy.l01")},
        True,
    ),
    ("search", "search_records", {"key": "xenonol"}, False),
    ("search by CAS", "search_records", {"key": "999-99-5", "scheme": "cas", "limit": 1}, False),
    ("search water", "search_records", {"key": "water", "limit": 2}, False),
    ("search a scheme without a key", "search_records", {"scheme": "cas"}, True),
    ("get", "get_record", {"record_sha256": SHA}, False),
    ("get absent", "get_record", {"record_sha256": ABSENT}, True),
    ("validate", "validate_record", {"record": user_component()}, False),
    ("validate a refused record", "validate_record", {"record": {**SECOND, "name": ""}}, False),
    ("validate absent", "validate_record", {"records": [ABSENT]}, True),
    ("assess", "assess_rights", RIGHTS_ROW, False),
    ("assess the source", "assess_rights", {**RIGHTS_ROW, "scope": "source"}, False),
    ("assess a foreign source", "assess_rights", {**RIGHTS_ROW, "source_id": "user.x"}, True),
    ("assess absent", "assess_rights", {**RIGHTS_ROW, "record_sha256": ABSENT}, True),
    ("get assessed", "get_record", {"record_sha256": SHA}, False),
)
#: Clock readings (a registration's `at`, a rights row's `date`).
CLOCK = frozenset({"at", "date"})


def _stable(document: Any, caller: str) -> Any:
    """`document` without its clock members, with the caller's principal id as `<caller>`."""
    if isinstance(document, dict):
        return {k: _stable(v, caller) for k, v in document.items() if k not in CLOCK}
    if isinstance(document, list):
        return [_stable(item, caller) for item in document]
    return "<caller>" if document == caller else document


def _refusal(app: LocalApplication, name: str, request: dict[str, Any]) -> dict[str, Any]:
    with pytest.raises(ApplicationError) as refused:
        dispatch(app, name, request)
    document = refused.value.error.as_document()
    assert isinstance(document, dict)
    return document


def _source_sha256(source_id: str, entry: dict[str, Any]) -> str:
    """D11: SHA-256 of the canonical one-member object `{source_id: entry}` (ADR 0002)."""
    text = json.dumps({source_id: entry}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ================================================================================ E-F3-11


Outcomes = dict[str, dict[str, tuple[bool, Any]]]


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> Outcomes:
    """`SCENARIO` on Python, CLI, HTTP and MCP, each over its own fresh project:
    `{label: {transport: (is an error, document)}}`."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    root = tmp_path_factory.mktemp("f3-operations")
    projects = {name: root / name for name in ("python", "cli", "http", "mcp")}
    for project in projects.values():
        LocalApplication.create(project, project_id="f3-operations").close()
    granted = {
        name: grant(
            projects[name],
            principal_id=AGENT,
            rights=("read", "draft", "policy"),
            limits=Limits(default_wall_time_s=60.0, max_wall_time_s=60.0, max_active_jobs=1),
            capability_id="cap-f3",
        )
        for name in ("http", "mcp")
    }
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    found: Outcomes = {}
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        clients: dict[str, Client] = {
            "python": PythonInline(projects["python"]),
            "cli": CliClient(projects["cli"], root / "raw.bin", out, err),
            "http": HttpClient(projects["http"], granted["http"][1]),
            "mcp": McpClient(projects["mcp"], granted["mcp"][0]),
        }
        try:
            for label, name, request, _ in SCENARIO:
                found[label] = {
                    transport: client.call(name, request) for transport, client in clients.items()
                }
        finally:
            for client in clients.values():
                client.close()
    return found


def test_e_f3_11_each_step_gives_one_document_on_every_transport(outcomes: Outcomes) -> None:
    callers = {"python": LOCAL_OWNER_PRINCIPAL, "cli": LOCAL_OWNER_PRINCIPAL}
    callers |= {"http": AGENT, "mcp": AGENT}
    assert {name for _, name, _, _ in SCENARIO} == F3_OPERATIONS
    assert all(
        {"cli", "http", "mcp", "python"} <= set(OPERATIONS[n].transports) for n in F3_OPERATIONS
    )
    for label, _, _, refused in SCENARIO:
        each = outcomes[label]
        assert sorted(each) == ["cli", "http", "mcp", "python"]
        expected = _stable(each["python"][1], LOCAL_OWNER_PRINCIPAL)
        for transport, (error, document) in each.items():
            assert error is refused, (label, transport, document)
            stable = _stable(document, callers[transport])
            assert canonical_json(stable) == canonical_json(expected), (label, transport)
    # Each operation succeeds at least once and is refused at least once.
    for name in ("search_records", "get_record", "register_record", "validate_record"):
        assert {refused for _, n, _, refused in SCENARIO if n == name} == {False, True}


def test_e_f3_11_the_scenarios_documents_are_d13s(outcomes: Outcomes) -> None:
    """D13's promises on the Python column (the others equal it): idempotent by content, the
    store each record is read from, a row of the caller's, `not_found` naming the SHA."""
    python = {label: each["python"][1] for label, each in outcomes.items()}
    first, again = python["register"]["results"], python["register again"]["results"]
    assert [item["created"] for item in first + again] == [True, False]
    assert first[0]["record_sha256"] == again[0]["record_sha256"] == SHA
    assert python["search"]["items"][0]["store"] == "project"
    assert {item["store"] for item in python["search water"]["items"]} == {"legacy"}
    assert python["get"]["store"] == "project"
    assert python["get"]["rights"]["rows"] == []
    assert python["get absent"]["code"] == "not_found"
    assert python["get absent"]["detail"]["record_sha256"] == ABSENT
    assert python["validate"] == {**python["validate"], "errors": [], "record_sha256": SHA}
    assert python["validate a refused record"]["record_sha256"] is None
    assert python["validate a refused record"]["errors"][0]["code"] == "record_schema_invalid"
    rows = python["get assessed"]["rights"]["rows"]
    assert [(row["sequence"], row["layer"], row["record_sha256"]) for row in rows] == [
        (1, "project", SHA),
        (2, "project", None),
    ]
    assert {row["decided_by"] for row in rows} == {LOCAL_OWNER_PRINCIPAL}


@contextlib.contextmanager
def _captured() -> Iterator[tuple[io.StringIO, io.StringIO]]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def _cli(*argv: str) -> tuple[int, Any]:
    with _captured() as (out, _):
        code = main(["records", *argv])
    return code, json.loads(out.getvalue())


def _direct(project: Path, name: str, request: dict[str, Any]) -> tuple[int, Any]:
    """`dispatch` as the local owner: `(exit code as the CLI gives it, document)`."""
    with LocalApplication.open(project) as app:
        try:
            return 0, dispatch(app, name, request)
        except ApplicationError as refused:
            document = refused.error.as_document()
            return API_EXIT_CODES[document["code"]], document


def test_e_f3_11_the_cli_conveniences_print_the_operations_documents(tmp_path: Path) -> None:
    project = tmp_path / "project"
    LocalApplication.create(project).close()
    at = ("--project", str(project))
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps(user_component()), encoding="utf-8")
    code, registered = _cli("register", "--record", str(record_file), *at)
    with LocalApplication.in_memory() as fresh:
        assert (code, registered) == (
            0,
            dispatch(fresh, "register_record", {"record": user_component()}),
        )
    for argv, name, request in (
        (("search", "--key", "xenonol"), "search_records", {"key": "xenonol", "limit": 50}),
        (
            (
                "search",
                "--key",
                "999-99-5",
                "--scheme",
                "cas",
                "--type",
                "component",
                "--limit",
                "1",
            ),
            "search_records",
            {"key": "999-99-5", "scheme": "cas", "record_type": "component", "limit": 1},
        ),
        (("get", SHA), "get_record", {"record_sha256": SHA}),
        (("get", ABSENT), "get_record", {"record_sha256": ABSENT}),
        (
            ("validate", "--record", str(record_file)),
            "validate_record",
            {"record": user_component()},
        ),
    ):
        assert _cli(*argv, *at) == _direct(project, name, request), argv
    # A user file: the record it holds, as `register_record` stores it (E-F3-12's round trip).
    data_file = tmp_path / "second.json"
    data_file.write_text(json.dumps(SECOND), encoding="utf-8")
    code, filed = _cli("register", "--file", str(data_file), "--format", "record-v2-json", *at)
    with LocalApplication.in_memory() as fresh:
        assert (code, filed) == (0, dispatch(fresh, "register_record", {"record": SECOND}))
    code, assessed = _cli(
        "rights",
        "--source",
        "user.lab",
        "--record",
        SHA,
        "--scope",
        "source",
        "--assessment",
        "refused",
        "--basis",
        "a test",
        *at,
    )
    row = assessed["row"]
    assert code == 0
    assert (row["record_sha256"], row["assessment"], row["decided_by"], row["sequence"]) == (
        None,
        "refused",
        LOCAL_OWNER_PRINCIPAL,
        1,
    )
    assert _cli("get", SHA, *at)[1]["rights"]["rows"] == [{**row, "layer": "project"}]


def test_e_f3_11_a_records_command_with_an_unreadable_file_makes_no_call(tmp_path: Path) -> None:
    project = tmp_path / "project"
    LocalApplication.create(project).close()
    with _captured() as (out, err):
        code = main(
            ["records", "register", "--record", str(tmp_path / "x.json"), "--project", str(project)]
        )
    assert (code, out.getvalue()) == (1, "")
    assert "cannot read the input" in err.getvalue()


def test_e_f3_11_every_code_of_the_records_paths_has_a_complete_entry() -> None:
    """Every code MSG-G2's scan finds in `records/` and the Records service, and the ones the
    service raises by name (`reserved_namespace`, ADR 0060's; `not_found`'s record variant)."""
    found = msg_catalogue.scan()
    sites = {
        code
        for code, places in found.items()
        if any("openflowsheet/records/" in p or "records_service.py" in p for p in places)
    }
    assert sites, "the scan reaches the records package"
    for code in sites | {"reserved_namespace", "not_found", "data_unavailable"}:
        entry = CATALOGUE.entry(code)
        assert entry is not None and entry.complete, code
    assert "record_sha256" in CATALOGUE.entry("not_found").params
    assert msg_catalogue.scan_misses(CATALOGUE.keys()) == {}


# ======================================================= D11: the reserved namespace `legacy.`


@pytest.fixture
def app() -> Iterator[LocalApplication]:
    with LocalApplication.in_memory() as application:
        yield application


def _legacy_record(app: LocalApplication) -> tuple[str, dict[str, Any]]:
    """An indexed legacy record (water, `legacy.l01`) as the legacy store serves it."""
    (item,) = app.search_records(key="7732-18-5", scheme="cas", limit=50).items[:1]
    view = app.get_record(item["record_sha256"])
    assert view.store == "legacy"
    return view.record_sha256, dict(view.record)


def _assert_reserved(refused: dict[str, Any], **at: Any) -> None:
    assert refused["code"] == "invalid_request"
    detail = refused["detail"]
    assert detail["reason"] == "reserved_namespace"
    assert detail["refusal"] == {"code": "reserved_namespace", "params": {"namespace": "legacy"}}
    for name, value in at.items():
        assert detail[name] == value, name


def test_d11_an_indexed_legacy_record_is_copied_into_the_project_store(
    app: LocalApplication,
) -> None:
    sha, record = _legacy_record(app)
    assert any(source.startswith("legacy.") for source in record["sources"])
    result = dispatch(app, "register_record", {"record": record})
    assert [(item["record_sha256"], item["created"]) for item in result["results"]] == [(sha, True)]
    assert app.get_record(sha).store == "project"


def test_d11_a_forged_legacy_source_is_refused_and_nothing_is_stored(
    app: LocalApplication,
) -> None:
    forged = user_component("user.zenonol", "zenonol", source="legacy.l01")
    _assert_reserved(_refusal(app, "register_record", {"record": forged}), pointer="/record")
    # An indexed record with one value changed is no longer the importer's.
    _, record = _legacy_record(app)
    changed = json.loads(json.dumps(record))
    changed["molar_mass"]["value"] *= 1.0 + 1e-9
    _assert_reserved(_refusal(app, "register_record", {"record": changed}))
    assert app.search_records(key="zenonol").items == ()
    every = app.search_records(limit=200).items
    assert [item for item in every if item["store"] == "project"] == []


def test_d11_a_user_files_legacy_defaults_source_is_refused() -> None:
    content = (REPO_ROOT / "benchmarks" / "m01" / "components.yaml").read_text(encoding="utf-8")
    defaults = {
        "origin": ["measured"],
        "derivation": "direct",
        "source_id": "legacy.m01",
        "source_version": "2026-11-18",
        "citation": "a copy claiming the legacy source",
    }
    with LocalApplication.in_memory() as app:
        request = {
            "file": {"format": "component-record-v1-yaml", "content": content},
            "defaults": defaults,
        }
        _assert_reserved(
            _refusal(app, "register_record", request), pointer="/file/content", record_index=0
        )
        allowed = {**request, "defaults": {**defaults, "source_id": "user.m01-copy"}}
        stored = dispatch(app, "register_record", allowed)["results"]
        assert len(stored) == 5 and all(item["created"] for item in stored)
    # A v2 file naming the source in `sources`.
    forged = user_component("user.zenonol", "zenonol", source="legacy.s07")
    with LocalApplication.in_memory() as app:
        file = {"format": "record-v2-json", "content": json.dumps([SECOND, forged])}
        _assert_reserved(
            _refusal(app, "register_record", {"file": file}),
            pointer="/file/content",
            record_index=1,
        )
        assert app.search_records(key="yenonol").items == (), "a refused file stores nothing"


# ============================================== D13: `assess_rights`' request validation


def test_d13_an_unknown_record_sha256_is_not_found(app: LocalApplication) -> None:
    refused = _refusal(app, "assess_rights", {**RIGHTS_ROW, "record_sha256": ABSENT})
    assert refused["code"] == "not_found"
    assert (refused["detail"]["record_sha256"], refused["detail"]["pointer"]) == (
        ABSENT,
        "/record_sha256",
    )


def test_d13_a_source_id_not_among_the_records_sources_is_invalid_request(
    app: LocalApplication,
) -> None:
    app.register_record(record=user_component())
    refused = _refusal(app, "assess_rights", {**RIGHTS_ROW, "source_id": "user.other"})
    assert refused["code"] == "invalid_request"
    assert refused["detail"]["pointer"] == "/source_id"
    assert app.get_record(SHA).rows == ()


def test_d13_scope_record_and_scope_source_write_d11s_rows(app: LocalApplication) -> None:
    app.register_record(record=user_component())
    entry = app.get_record(SHA).record["sources"]["user.lab"]
    source_sha256 = _source_sha256("user.lab", dict(entry))
    on_record = dispatch(app, "assess_rights", RIGHTS_ROW)["row"]
    on_source = dispatch(
        app, "assess_rights", {**RIGHTS_ROW, "scope": "source", "conditions": "cite the lab"}
    )["row"]
    for row in (on_record, on_source):
        assert (row["source_id"], row["source_sha256"]) == ("user.lab", source_sha256)
        assert (row["decided_by"], row["layer"], row["basis"]) == (
            LOCAL_OWNER_PRINCIPAL,
            "project",
            RIGHTS_ROW["basis"],
        )
    assert (on_record["record_sha256"], on_record["conditions"]) == (SHA, None)
    assert (on_source["record_sha256"], on_source["conditions"]) == (None, "cite the lab")
    # The whole-source row is keyed by `source_sha256`: another record of the same source entry
    # takes it; a record naming the same id with another entry does not (D11).
    other = user_component("user.other", "other")
    other["identifiers"] = {"cas": "50-00-0"}
    other_sha = app.register_record(record=other).results[0]["record_sha256"]
    assert app.get_record(other_sha).effective["user.lab"]["assessment"] == "permitted"
    moved = user_component("user.moved", "moved")
    moved["identifiers"] = {"cas": "64-17-5"}
    moved["sources"]["user.lab"]["version"] = "2"
    moved_sha = app.register_record(record=moved).results[0]["record_sha256"]
    assert app.get_record(moved_sha).effective["user.lab"]["assessment"] == "unknown"


def test_d13_each_call_writes_one_audit_row(app: LocalApplication) -> None:
    app.register_record(record=user_component())
    before = len(app.store.audit_rows())
    sequence = dispatch(app, "assess_rights", RIGHTS_ROW)["row"]["sequence"]
    rows = app.store.audit_rows()
    assert len(rows) == before + 1
    assert (rows[-1]["operation"], rows[-1]["outcome"], rows[-1]["effect"]) == (
        "assess_rights",
        "allowed",
        f"rights:{sequence}",
    )
    _refusal(app, "assess_rights", {**RIGHTS_ROW, "source_id": "user.other"})
    assert len(app.store.audit_rows()) == before + 2


def test_d13_latest_is_the_highest_insertion_sequence_not_the_date(app: LocalApplication) -> None:
    app.register_record(record=user_component())
    first = dispatch(app, "assess_rights", {**RIGHTS_ROW, "assessment": "refused"})
    second = dispatch(app, "assess_rights", {**RIGHTS_ROW, "assessment": "permitted"})
    assert (first["row"]["sequence"], second["row"]["sequence"]) == (1, 2)
    assert first["row"]["date"] == second["row"]["date"], "the same day: only the order decides"
    assert second["effective"] == {
        "assessment": "permitted",
        "conditions": None,
        "layer": "project",
    }
    third = dispatch(app, "assess_rights", {**RIGHTS_ROW, "assessment": "unknown"})
    assert third["effective"]["assessment"] == "unknown"
    view = app.get_record(SHA)
    assert [row["sequence"] for row in view.rows] == [1, 2, 3]
    assert view.effective["user.lab"]["assessment"] == "unknown"


# ===================================== F3 review 2 (R-1052 to R-1057), the fix round's C items


def _alias_bomb(tail: str) -> str:
    """M1's file: 24 nested aliases (`aN: &aN [*aN-1, *aN-1]`, 2^24 leaves) before `tail`."""
    lines = ["a0: &a0 [x, x]", *(f"a{n}: &a{n} [*a{n - 1}, *a{n - 1}]" for n in range(1, 24))]
    return "\n".join([*lines, tail])


@pytest.mark.parametrize(
    "file_format", ["record-v2-yaml", "component-record-v1-yaml"], ids=["v2", "v1"]
)
def test_c1_a_yaml_alias_is_refused_before_it_expands(
    app: LocalApplication, file_format: str
) -> None:
    """R-1057: a user file's YAML may not use an alias; the 903-character file of M1 took 292 s
    before the fix and is refused here at once, nothing stored."""
    tail = "components: []" if file_format.startswith("component") else "name: xenonol"
    request = {"file": {"format": file_format, "content": _alias_bomb(tail)}}
    started = time.perf_counter()
    refused = _refusal(app, "register_record", request)
    elapsed = time.perf_counter() - started
    assert refused["code"] == "invalid_request"
    assert refused["detail"]["reason"] == "record_schema_invalid"
    assert elapsed < 1.0, elapsed
    # One alias of one scalar is refused as well: the rule is the alias, not its size.
    small = "- &h2 {name: h2}\n- *h2\n"
    refused = _refusal(app, "register_record", {"file": {"format": file_format, "content": small}})
    assert refused["detail"]["reason"] == "record_schema_invalid"
    assert [i for i in app.search_records(limit=200).items if i["store"] == "project"] == []
