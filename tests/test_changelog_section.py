"""`scripts/changelog_section.py`: the release notes of `.github/workflows/release.yml` are the
version's `CHANGELOG.md` section (docs/RELEASING.md)."""

from __future__ import annotations

import sys

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import changelog_section  # noqa: E402

CHANGELOG = """# Changelog

## v0.2.0 — 2027-01-01

Second.

### Details

More.

## v0.1.0rc1 — a candidate

Candidate.

## v0.1.0 — the first

First.

## v0.0.9

"""


def test_changelog_section_is_the_body_up_to_the_next_level_2_heading() -> None:
    assert changelog_section.section(CHANGELOG, "v0.2.0") == "Second.\n\n### Details\n\nMore.\n"
    assert changelog_section.section(CHANGELOG, "v0.1.0") == "First.\n"


def test_changelog_section_refusals() -> None:
    with pytest.raises(changelog_section.MissingSectionError, match="0 sections"):
        changelog_section.section(CHANGELOG, "v0.3.0")
    with pytest.raises(changelog_section.MissingSectionError, match="empty"):
        changelog_section.section(CHANGELOG, "v0.0.9")
    with pytest.raises(changelog_section.MissingSectionError, match="2 sections"):
        changelog_section.section(CHANGELOG + "## v0.1.0\n\nAgain.\n", "v0.1.0")
    with pytest.raises(ValueError, match="vX.Y.Z"):
        changelog_section.section(CHANGELOG, "0.1.0")


def test_changelog_section_of_the_repository() -> None:
    """The v0.1.0 notes are the repository changelog's own section, starting with ADR 0021 D4's
    italic preamble and stopping before v0.0.0."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = changelog_section.section(text, "v0.1.0")
    assert notes.startswith("*ADR 0021 D4.")
    assert "## v0.0.0" not in notes and "## v0.1.0" not in notes
    assert notes.strip() in text
