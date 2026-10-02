"""T08.A18: the MCP tool descriptions are reviewed by both lanes (T08 review 2, Ruling 13).

T07 §11.3 made two reviews of each of the 17 agent-facing texts conditions: the design lane's and
Frank's. Ruling 13 makes the design-lane review an RC blocker, not a limitation: this test asserts
that `bindings/descriptions/REVIEW.json` records, for every MCP operation, both reviews
`reviewed`, with `reviewed_by` and `reviewed_at` set, at the recorded hash — and that the recorded
hash is the served text's (the file `bindings/mcp.py`'s `description` serves, read the same way).

**It stays red until the reviews are recorded** (no xfail). Recording them is the reviewers' act,
in `REVIEW.json`; no agent marks a review done on its own work, and a changed text voids its
reviews (its hash moves).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from conftest import REPO_ROOT

from openflowsheet.application.operations import OPERATIONS

BINDINGS = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings"
REVIEW = BINDINGS / "descriptions" / "REVIEW.json"
MCP_OPERATIONS = sorted(name for name, op in OPERATIONS.items() if "mcp" in op.transports)
REVIEW_KINDS = ("design-lane", "human")


def test_every_description_is_reviewed_by_both_lanes() -> None:
    record: dict[str, Any] = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert len(MCP_OPERATIONS) == 17
    assert sorted(record["operations"]) == MCP_OPERATIONS

    open_items: list[str] = []
    for name in MCP_OPERATIONS:
        entry = record["operations"][name]
        described = OPERATIONS[name].description_file
        assert described is not None, name
        served = (BINDINGS / described).read_text(encoding="utf-8")
        if hashlib.sha256(served.encode("utf-8")).hexdigest() != entry["sha256"]:
            open_items.append(f"{name}: the recorded hash is not the served text's")
        reviews = {review["review_kind"]: review for review in entry["reviews"]}
        for kind in REVIEW_KINDS:
            review = reviews.get(kind)
            if review is None:
                open_items.append(f"{name}: no {kind} review")
            elif not (
                review["status"] == "reviewed" and review["reviewed_by"] and review["reviewed_at"]
            ):
                open_items.append(f"{name}: {kind} {review['status']}")
    assert open_items == [], f"{len(open_items)} open: {open_items}"
