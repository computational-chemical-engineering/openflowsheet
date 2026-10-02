"""P00 baseline: the authoritative documents are the ones the plan was written against.

`docs/implementation-plan.md` records the blueprint's SHA-256 in its header. If either document
is edited, this test fails and the edit must be made deliberately (CLAUDE.md, "Authority").
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import sha256_of

BASELINE_LINE = re.compile(r"^\*\*Baseline SHA-256:\*\*\s*`([0-9a-f]{64})`\s*$", re.MULTILINE)
PLAN_VERSION_LINE = re.compile(r"^\*\*Plan version:\*\*\s*(\d+\.\d+)", re.MULTILINE)


def plan_recorded_blueprint_hash(repo_root: Path) -> str:
    text = (repo_root / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    match = BASELINE_LINE.search(text)
    assert match is not None, "implementation plan header has no `Baseline SHA-256:` line"
    return match.group(1)


def test_blueprint_hash_matches_plan_header(repo_root: Path) -> None:
    actual = sha256_of(repo_root / "docs" / "blueprint-v3.1.md")
    assert actual == plan_recorded_blueprint_hash(repo_root)


def test_plan_version_is_the_execution_authority(repo_root: Path) -> None:
    text = (repo_root / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    match = PLAN_VERSION_LINE.search(text)
    assert match is not None, "implementation plan header has no `Plan version:` line"
    # 1.2 (2026-09-24): the two-model protocol restated as two lanes; terminology only.
    assert match.group(1) == "1.2"
