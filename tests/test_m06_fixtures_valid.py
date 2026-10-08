"""M06 WO-7 (design note §8 Layer A 5): the web fixtures cannot drift from the contract silently.

`tests/web/fixtures/w26/` (`scripts/m06_web_fixtures.py`) holds the server's answers the Node
tests feed to the shell. Each record is held here to the contract as it stands: its key names an
`OPERATIONS` row the shell may call with a request that row's schema accepts; a 200 answer
satisfies the operation's response schema; a refusal is an `ApiError` document at its code's
HTTP status; every raw record's bytes are the bytes the bundle listing registered (SHA-256 and
size) and satisfy the record schema of their kind. The project is §8's: the five revisions and
three jobs it names, the outcomes it names, and the audit rows of exactly the build's effects and
refusals. No bearer token is in the fixtures.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from test_m06_static_scan import UI_OPERATIONS

from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.types import ApiError, schema_errors, validate_inline

FIXTURES = REPO_ROOT / "tests" / "web" / "fixtures" / "w26"
#: The record schema of each bundle member kind (`solve_trace` is an array of solve events).
KIND_SCHEMA = {
    "execution_plan": "execution-plan.schema.json",
    "failure_bundle": "failure-bundle.schema.json",
    "revision_document": "process-revision.schema.json",
    "run_manifest": "run-manifest.schema.json",
    "solution_certificate": "solution-certificate.schema.json",
    "solution_state": "solution-state.schema.json",
    "solve_plan": "solve-plan.schema.json",
    "solve_policy": "solve-policy.schema.json",
}
#: Kinds `schemas/` publishes no record schema for (checked to be JSON objects only).
NO_RECORD_SCHEMA = {"check_policy", "solve_path", "structural_report"}


@cache
def _fixture() -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FIXTURES / "exchanges.json").read_text("utf-8"))
    return document


def _check_record(schema_file: str, document: Any) -> None:
    """`document` against `schemas/<schema_file>`, whichever base its `$id` is published under."""
    schema_id = json.loads((REPO_ROOT / "schemas" / schema_file).read_text("utf-8"))["$id"]
    validate_inline(schema_file, {"$ref": schema_id}, document)


def _records() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """`(principal or "shared", key, record)` of every record."""
    for key, record in _fixture()["shared"].items():
        yield "shared", key, record
    for principal, records in _fixture()["principals"].items():
        for key, record in records.items():
            yield principal, key, record


def _parse(key: str) -> tuple[str, dict[str, Any]]:
    name, _, members = key.partition(" ")
    args: dict[str, Any] = json.loads(members)
    return name, args


RECORDS = sorted((owner, key) for owner, key, _ in _records())


def _record(owner: str, key: str) -> dict[str, Any]:
    found: dict[str, Any] = (
        _fixture()["shared"] if owner == "shared" else _fixture()["principals"][owner]
    )[key]
    return found


@pytest.mark.parametrize(("owner", "key"), RECORDS)
def test_every_record_is_a_schema_valid_exchange(owner: str, key: str) -> None:
    name, args = _parse(key)
    assert name in UI_OPERATIONS, name
    operation = OPERATIONS[name]
    validate_inline(name, operation.request_schema, args)
    record = _record(owner, key)
    if record["status"] != 200:
        error = ApiError.from_document(record["body"])
        assert record["status"] == error.http_status
        assert schema_errors("api-error.schema.json", record["body"]) == []
        return
    if operation.response_schema is None:
        assert set(record) == {"status", "raw"}
        assert (FIXTURES / record["raw"]).is_file()
        return
    assert set(record) == {"status", "body"}
    validate_inline(name, operation.response_schema, record["body"])


def _listed() -> dict[str, dict[str, Any]]:
    """Every bundle member the recorded listings register, by artifact id (the views of the
    listing hold the member rows whole: the listings are small)."""
    found: dict[str, dict[str, Any]] = {}
    for key, record in _fixture()["shared"].items():
        name, args = _parse(key)
        if name == "get_artifact" and args["pointer"] == "":
            for member in record["body"]["value"]["files"]:
                found[member["artifact_id"]] = member
    return found


def test_every_raw_record_is_the_registered_bytes_of_a_valid_record() -> None:
    listed = _listed()
    raw = {
        _parse(key)[1]["artifact_id"]: record
        for key, record in _fixture()["shared"].items()
        if _parse(key)[0] == "artifact_bytes"
    }
    assert set(raw) == set(listed)  # every member of every listing, and nothing else
    on_disk = {path.relative_to(FIXTURES).as_posix() for path in (FIXTURES / "raw").rglob("*")}
    assert {record["raw"] for record in raw.values()} == {p for p in on_disk if p.endswith(".json")}
    kinds: set[str] = set()
    for artifact_id, record in sorted(raw.items()):
        member = listed[artifact_id]
        data = (FIXTURES / record["raw"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == member["sha256"], artifact_id
        assert len(data) == member["size_bytes"], artifact_id
        document = json.loads(data)
        kind = member["kind"]
        kinds.add(kind)
        if kind == "solve_trace":
            assert isinstance(document, list) and document
            for event in document:
                _check_record("solve-event.schema.json", event)
        elif kind in KIND_SCHEMA:
            _check_record(KIND_SCHEMA[kind], document)
        else:
            assert kind in NO_RECORD_SCHEMA, kind
            assert isinstance(document, dict)
    assert kinds == set(KIND_SCHEMA) | NO_RECORD_SCHEMA | {"solve_trace"}


def test_the_project_is_the_one_section_8_names() -> None:
    fixture = _fixture()
    assert fixture["revisions"] == {
        "NET02": "rev-000001",
        "NET02-split-0.90": "rev-000002",
        "STR03": "rev-000003",
        "A02-352": "rev-000004",
        "hostile": "rev-000005",
    }
    assert fixture["jobs"] == {
        "NET02": "job-000001",
        "NET02-split-0.90": "job-000002",
        "A02-352": "job-000003",
    }
    outcomes = {}
    for key, record in fixture["shared"].items():
        name, args = _parse(key)
        if name == "get_job_result":
            run = record["body"]["run_result"]
            outcomes[args["job_id"]] = (run["outcome"], run["verification_status"])
        if name == "validate":
            status = record["body"]["status"]
            assert (status == "INVALID") == (args["revision_id"] == "rev-000003"), args
    assert outcomes == {
        "job-000001": ("CONVERGED", "VERIFIED"),
        "job-000002": ("CONVERGED", "VERIFIED"),
        "job-000003": ("HOMOTOPY_STALLED", None),
    }


def test_the_history_is_exactly_the_builds_effects_and_refusals() -> None:
    every = _record("supervisor-c", 'list_audit {"limit":200,"order":"descending"}')["body"]
    assert every["next_cursor"] is None
    rows = [
        (row["principal_id"], row["operation"], row["outcome"], row["effect"], row["code"])
        for row in reversed(every["items"])
    ]
    assert rows[4:] == [
        ("agent-a", "commit_change", "allowed", "revision:rev-000001", None),
        ("agent-a", "submit_job", "allowed", "job:job-000001", None),
        ("agent-a", "commit_change", "allowed", "revision:rev-000002", None),
        ("agent-a", "submit_job", "allowed", "job:job-000002", None),
        ("agent-a", "commit_change", "allowed", "revision:rev-000003", None),
        ("agent-a", "commit_change", "allowed", "revision:rev-000004", None),
        ("agent-a", "submit_job", "allowed", "job:job-000003", None),
        ("agent-a", "commit_change", "allowed", "revision:rev-000005", None),
        ("viewer-b", "submit_job", "refused", None, "forbidden"),
        ("viewer-b", "list_audit", "refused", None, "forbidden"),
    ]
    assert [row[1] for row in rows[:4]] == ["project_init"] + ["project_grant"] * 3
    refused = _record("viewer-b", 'list_audit {"limit":200,"order":"descending"}')
    assert (refused["status"], refused["body"]["code"]) == (403, "forbidden")


def test_no_bearer_token_is_in_the_fixtures() -> None:
    for path in FIXTURES.rglob("*"):
        if path.is_file():
            assert b"prt_" not in path.read_bytes(), path


def test_the_fixture_files_are_listed_in_the_readme() -> None:
    readme = (REPO_ROOT / "tests" / "web" / "fixtures" / "README.md").read_text("utf-8")
    files = sorted(
        path.relative_to(FIXTURES.parent).as_posix()
        for path in FIXTURES.parent.rglob("*")
        if path.is_file() and path.name != "README.md"
    )
    missing = [name for name in files if f"`{name}`" not in readme]
    assert missing == []
    assert Path(__file__).name in readme
