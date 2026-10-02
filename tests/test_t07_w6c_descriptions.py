"""T07 W6c: the MCP tool descriptions and their review record (design note §11.3, gate G15).

The files `bindings/descriptions/<operation>.md` are the text the MCP server serves as each tool's
description, and `REVIEW.json` records each text's SHA-256 and the state of its two reviews. This
module holds the file half of G15 and runs in every environment; the served half (the text a real
stdio session lists) is in `test_t07_w6b_mcp.py`, which needs the `server` extra.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.projection import is_forbidden
from openflowsheet.application.revision_binding import target_path_table
from openflowsheet.models.revision_flowsheet import TARGET_PATH_KINDS, si_unit

DESCRIPTIONS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings" / "descriptions"
#: §11.3.
MAX_CHARACTERS = 1500
MCP_OPERATIONS = sorted(name for name, op in OPERATIONS.items() if "mcp" in op.transports)
#: The statuses a review may hold. Setting one to done is the reviewer's act, never the author's.
REVIEW_STATUSES = {
    "design-lane": {"pending_design_review", "reviewed", "changes_requested"},
    "human": {"pending", "reviewed", "changes_requested"},
}


@pytest.fixture(scope="module")
def review() -> dict[str, Any]:
    document = json.loads((DESCRIPTIONS / "REVIEW.json").read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _text(name: str) -> str:
    return (DESCRIPTIONS / f"{name}.md").read_text(encoding="utf-8")


def test_g15_one_description_per_mcp_operation_and_no_other() -> None:
    assert len(MCP_OPERATIONS) == 17
    files = sorted(path.stem for path in DESCRIPTIONS.glob("*.md"))
    assert files == MCP_OPERATIONS
    for name in MCP_OPERATIONS:
        described = OPERATIONS[name].description_file
        assert described is not None
        assert Path(REPO_ROOT / "src/openflowsheet/application/bindings" / described) == (
            DESCRIPTIONS / f"{name}.md"
        )
    others = [name for name in OPERATIONS if name not in MCP_OPERATIONS]
    assert all(OPERATIONS[name].description_file is None for name in others)


@pytest.mark.parametrize("name", MCP_OPERATIONS)
def test_g15_the_file_is_the_reviewed_text_and_within_its_bound(
    name: str, review: dict[str, Any]
) -> None:
    text = _text(name)
    entry = review["operations"][name]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == entry["sha256"], (
        f"{name}.md changed: its reviews are void; record the new hash and re-request review"
    )
    assert len(text) == entry["characters"] <= MAX_CHARACTERS
    assert entry["tool"] == OPERATIONS[name].mcp_tool
    assert entry["file"] == f"{name}.md"


def test_g15_the_record_names_exactly_the_mcp_operations(review: dict[str, Any]) -> None:
    assert sorted(review["operations"]) == MCP_OPERATIONS


@pytest.mark.parametrize("name", MCP_OPERATIONS)
def test_the_two_reviews_are_recorded_and_none_is_claimed_without_a_reviewer(
    name: str, review: dict[str, Any]
) -> None:
    reviews = review["operations"][name]["reviews"]
    assert sorted(r["review_kind"] for r in reviews) == ["design-lane", "human"]
    for entry in reviews:
        assert entry["status"] in REVIEW_STATUSES[entry["review_kind"]]
        pending = entry["status"].startswith("pending")
        assert (entry["reviewed_by"] is None) == pending
        assert (entry["reviewed_at"] is None) == pending


@pytest.mark.parametrize("name", MCP_OPERATIONS)
def test_each_description_states_its_right_and_that_data_is_not_instruction(name: str) -> None:
    """§11.3: each states the right it needs; §10.6: authority is the credential's alone."""
    text = _text(name)
    assert f"Right needed: {OPERATIONS[name].right}" in text
    assert "authority comes only from this session's credential" in text
    assert not any(is_forbidden(character) for character in text if character not in "\n")


@pytest.mark.parametrize("name", MCP_OPERATIONS)
def test_a_paged_operation_says_how_to_page(name: str) -> None:
    """§11.3: how to page, for every operation whose request takes a cursor or a sequence."""
    members = set(OPERATIONS[name].request_schema.get("properties", {}))
    if members & {"cursor", "after_sequence"}:
        assert "next_cursor" in _text(name) or "after_sequence" in _text(name)
        if "cursor" in members:
            assert '"cursor"' in _text(name)


JOB_OPERATIONS = [
    "submit_job",
    "get_job",
    "list_jobs",
    "list_job_events",
    "wait_job",
    "cancel_job",
    "get_job_result",
]


@pytest.mark.parametrize("name", JOB_OPERATIONS)
def test_a_job_operation_says_what_completed_does_not_mean(name: str) -> None:
    """§11.3: `completed` is the operation's end, never convergence or verification (§5.5)."""
    text = _text(name)
    assert '"completed" means only that' in text or 'status "completed" means only' in text
    assert "converged" in text and "verif" in text


@pytest.mark.parametrize("name", ["submit_job", "get_job_result", "get_artifact", "list_jobs"])
def test_the_reproduce_readers_say_an_inspected_archive_is_not_verification(name: str) -> None:
    assert "inspected_archived_results" in _text(name)


@pytest.mark.parametrize("name", ["list_models", "commit_change", "preview_change"])
def test_the_target_path_table_is_the_generated_one(name: str) -> None:
    """T07 ruling round 6, B2 item 3: the six-row target-path table (object type, path, kind, SI
    unit, what it pins) and the line pointing at `list_models`, exactly as generated from the one
    target-path table the revision binder reads."""
    table = target_path_table()
    assert table in _text(name)
    rows = [line for line in table.splitlines() if line.startswith("- ")]
    assert len(rows) == len(TARGET_PATH_KINDS) == 6
    for row, (path, kind) in zip(rows, TARGET_PATH_KINDS.items(), strict=True):
        assert f" {path}" in row and f": {kind}, {si_unit(kind)}; " in row
