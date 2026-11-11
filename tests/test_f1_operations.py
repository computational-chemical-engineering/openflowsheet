"""F1-WO4a (ADR 0060 D11, ADR 0019 Amendment 7): `list_capabilities` and `check_admission`.

- **E-F1-10.** Three requests per operation return identical canonical documents on Python, the
  CLI, HTTP and MCP (each transport's own promises are checked by its client,
  `tests/t07_transport_support.py`); the CLI conveniences `capabilities` and `admission` print the
  same documents. Every code the registry emits has a complete catalogue entry and MSG-G2's scan
  sees the registry's `Coded(...)` sites. The MCP digest re-take is
  `tests/test_t08_w2_surface_digest.py::test_f1s_surface_move_decomposes_onto_x04s` and link c_9 of
  `tests/test_m07a_surface_chain.py`; the R4-G3 snapshots of the existing operations are
  `tests/test_t07_w5e_application_results.py` (`SNAPSHOT_F1` holds only the two new rows).
- D11's paging, filters, defaults and refusals, on the process registry.
- F1-WO4b: three draft-form requests (`DRAFT_REQUESTS`) give one document on every transport too;
  E-F1-11 and the draft form's own checks are `tests/test_f1_draft_admission.py`.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application import capabilities
from openflowsheet.application.authz import grant
from openflowsheet.application.cli import API_EXIT_CODES, main
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import Limits, schema_errors
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.registry import default_registry, usage

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import msg_catalogue  # noqa: E402

ADMITTED = {"pair": {"unit": "thermal.heater", "method": "coolprop-heos-v1"}}
REFUSED = {"pair": {"unit": "thermal.heater", "method": "wilson-ig-v2"}}
UNKNOWN = {"pair": {"unit": "thermal.heatr", "method": "coolprop-heos-v1"}}
#: E-F1-10's three requests per operation: a success, a second success, a refusal.
LIST_REQUESTS: tuple[dict[str, Any], ...] = (
    {"kind": "connection_definition"},
    {"kind": "unit_model", "id_prefix": "thermal.", "limit": 3},
    {"cursor": "not-a-cursor"},
)
ADMISSION_REQUESTS: tuple[dict[str, Any], ...] = (ADMITTED, REFUSED, UNKNOWN)


def _draft(model: str | None = None, schema_version: int = 1) -> dict[str, Any]:
    revision = CORPUS["SYN-001-T06-NET02"]()
    if model is not None:
        revision["instances"][0]["model"]["id"] = model
    return {"revision": {**revision, "schema_version": schema_version}}


#: F1-WO4b: the draft form's three: admitted, one instance refused, a schema_version 2 revision.
DRAFT_REQUESTS: tuple[dict[str, Any], ...] = (
    _draft(),
    _draft("thermal.heater"),
    _draft(schema_version=2),
)
#: ADR 0060's code table, and WO3's `factory_unavailable` (W3-10).
F1_CODES = {
    "capability_missing": "refusal",
    "capability_unknown": "refusal",
    "reserved_capability": "refusal",
    "reserved_namespace": "refusal",
    "namespace_conflict": "refusal",
    "extension_invalid": "refusal",
    "extension_load_failed": "refusal",
    "self_hash_unavailable": "refusal",
    "platform_unsupported": "refusal",
    "dependency_missing": "refusal",
    "factory_unavailable": "refusal",
    "registry_closed": "refusal",
    "extension_unreviewed": "notice",
    "preview_kind": "notice",
    "capability_unresolved": "notice",
}


def _dispatch(request: dict[str, Any], name: str) -> tuple[bool, Any]:
    with LocalApplication.in_memory() as app:
        try:
            return False, dispatch(app, name, request)
        except ApplicationError as refused:
            return True, refused.error.as_document()


# ================================================================================ E-F1-10


Outcomes = dict[tuple[str, int], dict[str, tuple[bool, Any]]]


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> Outcomes:
    """E-F1-10's requests on Python, CLI, HTTP and MCP, each over its own fresh project (HTTP and
    MCP as a `read` grant): `{(operation, request index): {transport: (is an error, document)}}`.
    The calls are made here, with the CLI's streams installed for their duration."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    root = tmp_path_factory.mktemp("f1-operations")
    projects = {name: root / name for name in ("python", "cli", "http", "mcp")}
    for project in projects.values():
        LocalApplication.create(project, project_id="f1-operations").close()
    granted = {
        name: grant(
            projects[name],
            principal_id="agent-f1",
            rights=("read",),
            limits=Limits(default_wall_time_s=60.0, max_wall_time_s=60.0, max_active_jobs=1),
            capability_id="cap-f1",
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
            for key, name, requests in (
                ("list_capabilities", "list_capabilities", LIST_REQUESTS),
                ("check_admission", "check_admission", ADMISSION_REQUESTS),
                ("check_admission (draft)", "check_admission", DRAFT_REQUESTS),
            ):
                for index, request in enumerate(requests):
                    found[(key, index)] = {
                        transport: client.call(name, request)
                        for transport, client in clients.items()
                    }
        finally:
            for client in clients.values():
                client.close()
    return found


@pytest.mark.parametrize(
    "name", ["list_capabilities", "check_admission", "check_admission (draft)"]
)
def test_e_f1_10_three_requests_give_one_document_on_every_transport(
    outcomes: Outcomes, name: str
) -> None:
    errors = []
    for index in range(3):
        each = outcomes[(name, index)]
        assert sorted(each) == ["cli", "http", "mcp", "python"]
        expected = each["python"]
        errors.append(expected[0])
        for transport, outcome in each.items():
            assert outcome[0] == expected[0], (name, index, transport)
            assert canonical_json(outcome[1]) == canonical_json(expected[1]), (
                name,
                index,
                transport,
            )
    # The three are two successes and one refusal.
    assert errors == [False, False, True]


@contextlib.contextmanager
def _captured() -> Iterator[tuple[io.StringIO, io.StringIO]]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


@pytest.mark.parametrize(
    ("argv", "name", "request_document"),
    [
        (
            ["capabilities", "--kind", "connection_definition"],
            "list_capabilities",
            LIST_REQUESTS[0],
        ),
        (
            ["capabilities", "--kind", "unit_model", "--prefix", "thermal.", "--limit", "3"],
            "list_capabilities",
            {**LIST_REQUESTS[1], "kind": ["unit_model"]},
        ),
        (
            ["capabilities", "--kind", "unit_model", "--kind", "property_method", "--limit", "9"],
            "list_capabilities",
            {"kind": ["unit_model", "property_method"], "limit": 9},
        ),
        (
            ["admission", "--unit", "thermal.heater", "--method", "wilson-ig-v2"],
            "check_admission",
            REFUSED,
        ),
        (
            ["admission", "--unit", "thermal.heatr", "--method", "coolprop-heos-v1"],
            "check_admission",
            UNKNOWN,
        ),
    ],
)
def test_e_f1_10_the_cli_conveniences_print_the_operations_documents(
    argv: list[str], name: str, request_document: dict[str, Any]
) -> None:
    with _captured() as (out, _):
        code = main(argv)
    refused, expected = _dispatch(request_document, name)
    text = out.getvalue()
    assert text.endswith("\n") and text[:-1].encode("utf-8") == canonical_json(expected)
    assert code == (API_EXIT_CODES[expected["code"]] if refused else 0)


def test_e_f1_10_the_admission_convenience_without_a_pair_makes_no_call() -> None:
    with _captured() as (out, err):
        assert main(["admission", "--unit", "thermal.heater"]) == 1
    assert out.getvalue() == "" and "--method" in err.getvalue()


def test_e_f1_10_every_registry_code_has_a_complete_entry_that_g2_finds() -> None:
    for code, family in F1_CODES.items():
        entry = CATALOGUE.entry(code)
        assert entry is not None and entry.complete and entry.family == family, code
    found = msg_catalogue.scan()
    registry_sites = {
        code
        for code, places in found.items()
        if any("openflowsheet/registry/" in place for place in places)
    }
    # Every `Coded(...)` code of the registry is scanned; `registry_closed` is raised as a
    # `RuntimeError` text and has its entry all the same.
    assert set(F1_CODES) - {"registry_closed"} <= registry_sites
    assert msg_catalogue.scan_misses(CATALOGUE.keys()) == {}


# ============================================================================ D11 semantics


def test_list_capabilities_pages_cover_every_descriptor_once_in_order() -> None:
    registry = default_registry()
    seen: list[tuple[str, str, str]] = []
    cursor = None
    while True:
        page = capabilities.capability_page(registry, cursor=cursor, limit=7)
        assert page.registry_sha256 == registry.registry_sha256
        seen += [(d.document["kind"], d.document["id"], d.document["version"]) for d in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen == [(d.kind, d.id, d.version) for d in registry.descriptors()]
    assert len(seen) == len(set(seen)) > 7


def test_list_capabilities_filters_and_items() -> None:
    registry = default_registry()
    page = capabilities.capability_page(
        registry, kind=["property_method"], id_prefix="wilson", limit=200
    )
    assert [item.document["id"] for item in page.items] == ["wilson-ig-v1", "wilson-ig-v2"]
    assert page.next_cursor is None
    item = page.as_document()["items"][0]
    entry = registry.resolve("property_method", "wilson-ig-v1")
    assert item == entry.as_document()
    for member in ("self_sha256", "descriptor_sha256", "origin", "evidence_class", "stability"):
        assert member in item
    assert (
        schema_errors("application-results.schema.json#/$defs/capability_page", page.as_document())
        == []
    )
    one = capabilities.capability_page(registry, kind="unit_model", id_prefix="thermal.")
    assert one.items and all(i.document["kind"] == "unit_model" for i in one.items)


@pytest.mark.parametrize("cursor", ["not-a-cursor", "WyJhIiwiYiJd", "WyJhIiwiYiIsInYxIl0"])
def test_a_cursor_this_list_did_not_issue_is_refused(cursor: str) -> None:
    refused, document = _dispatch({"cursor": cursor}, "list_capabilities")
    assert refused and document["code"] == "invalid_request"
    assert document["detail"]["pointer"] == "/cursor"


def test_check_admission_defaults_and_verdicts() -> None:
    registry = default_registry()
    admitted = capabilities.admission_report(registry, pair=ADMITTED["pair"]).as_document()
    assert admitted["admitted"] is True and admitted["registry_sha256"] == registry.registry_sha256
    (pair,) = admitted["pairs"]
    assert pair["definition"] == "nTP-v1" and pair["instance"] is None
    assert pair["unit_version"] == registry.resolve("unit_model", "thermal.heater").version
    assert pair["refusal"] is None
    refused = capabilities.admission_report(registry, pair=REFUSED["pair"]).as_document()
    (pair,) = refused["pairs"]
    assert refused["admitted"] is False and pair["refusal"]["code"] == "capability_missing"
    assert set(pair["refusal"]["params"]) == {"unit", "method", "capability"}
    verdict = registry.admit("thermal.heater", "wilson-ig-v2", "nTP-v1")
    assert verdict.refusal is not None and pair["refusal"] == verdict.refusal.as_document()
    for report in (admitted, refused):
        assert (
            schema_errors("application-results.schema.json#/$defs/admission_report", report) == []
        )


def test_admission_is_a_query_not_a_use() -> None:
    with usage() as used:
        capabilities.admission_report(default_registry(), pair=ADMITTED["pair"])
        capabilities.capability_page(default_registry())
    assert used.sorted() == ()


@pytest.mark.parametrize(
    ("pair", "detail"),
    [
        (UNKNOWN["pair"], {"kind": "unit_model", "id": "thermal.heatr"}),
        (
            {**ADMITTED["pair"], "method_version": "9.9.9"},
            {"kind": "property_method", "id": "coolprop-heos-v1", "version": "9.9.9"},
        ),
        ({**ADMITTED["pair"], "definition": "nTP-v2"}, {"kind": "connection_definition"}),
    ],
)
def test_an_unknown_id_or_version_is_not_found_with_suggestions(
    pair: dict[str, Any], detail: dict[str, Any]
) -> None:
    refused, document = _dispatch({"pair": pair}, "check_admission")
    assert refused and document["code"] == "not_found"
    assert detail.items() <= document["detail"].items()
    assert document["detail"]["suggestions"]
    assert document["detail"]["explanation"]["summary"].endswith("is registered.")


def test_the_draft_form_reads_a_revision() -> None:
    """WO4b: the draft form's verdicts (WO4a refused it `unsupported`)."""
    _, admitted = _dispatch(DRAFT_REQUESTS[0], "check_admission")
    assert admitted["admitted"] is True
    assert [pair["instance"] for pair in admitted["pairs"]] == [
        entry["id"] for entry in DRAFT_REQUESTS[0]["revision"]["instances"]
    ]
    refused, document = _dispatch({"revision": {"title": "t"}}, "check_admission")
    assert refused and document["code"] == "invalid_request"
    assert document["detail"]["pointer"] == "/revision/schema_version"


@pytest.mark.parametrize(
    "request_document",
    [{}, {"pair": ADMITTED["pair"], "revision": {}}, {"pair": {"unit": "thermal.heater"}}],
)
def test_exactly_one_form_is_required(request_document: dict[str, Any]) -> None:
    refused, document = _dispatch(request_document, "check_admission")
    assert refused and document["code"] == "invalid_request"


def test_a_refusal_is_audited() -> None:
    with LocalApplication.in_memory() as app:
        with pytest.raises(ApplicationError):
            app.check_admission(pair=UNKNOWN["pair"])
        rows = app.list_audit(operation="check_admission").items
    assert [(row.outcome, row.code) for row in rows] == [("refused", "not_found")]


def test_the_default_definition_needs_exactly_one_conn_requirement() -> None:
    registry = default_registry()
    unit = registry.resolve("unit_model", "thermal.heater")
    assert capabilities.default_definition(unit) == "nTP-v1"
    widened = type(unit)(**{**unit.__dict__, "document": {**unit.document, "requires": []}})
    assert capabilities.default_definition(widened) is None
    two = [["conn:nTP-v1", "conn:acme.slurry"]]
    either = type(unit)(**{**unit.__dict__, "document": {**unit.document, "requires": two}})
    assert capabilities.default_definition(either) is None


def test_several_kinds_travel_as_a_list_one_kind_as_a_string() -> None:
    """W4a-2: `kind` is one kind or a list (HTTP's query carries one value per member, §11.3);
    the list of one kind and the kind alone give the same page."""
    _, one = _dispatch({"kind": "unit_model", "limit": 200}, "list_capabilities")
    _, listed = _dispatch({"kind": ["unit_model"], "limit": 200}, "list_capabilities")
    assert canonical_json(one) == canonical_json(listed)
    _, both = _dispatch(
        {"kind": ["property_method", "unit_model"], "limit": 200}, "list_capabilities"
    )
    kinds = [item["kind"] for item in both["items"]]
    assert kinds == sorted(kinds) and set(kinds) == {"property_method", "unit_model"}
