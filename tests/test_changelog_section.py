"""`scripts/changelog_section.py`: the release notes of `.github/workflows/release.yml` are the
version's `CHANGELOG.md` section (docs/RELEASING.md). M07a.A22 (V02 alpha release spec §9.1): the
tag may be a PEP 440 pre-release, and Table T3 (read from `benchmarks/m07a/reference_values.yaml`,
which `v02a_reference.py --check` re-derives) fixes which heading is a tag's section."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
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


M07A = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "m07a" / "reference_values.yaml").read_text(encoding="utf-8")
)


def test_m07a_a22_the_tag_pattern_is_the_registered_one() -> None:
    assert changelog_section.TAG.pattern == M07A["targets"]["changelog_tag_pattern"]


@pytest.mark.parametrize(
    ("tag", "heading", "is_section"), M07A["truth_tables"]["T3_changelog_section"]
)
def test_m07a_a22_table_t3(tag: str, heading: str, is_section: bool) -> None:
    changelog = f"# Changelog\n\n{heading}\n\nThe section.\n\n## v0.0.1\n\nOlder.\n"
    if is_section:
        assert changelog_section.section(changelog, tag) == "The section.\n"
    else:
        with pytest.raises(changelog_section.MissingSectionError, match="0 sections"):
            changelog_section.section(changelog, tag)


@pytest.mark.parametrize("tag", M07A["truth_tables"]["T3_malformed_tags"])
def test_m07a_a22_a_malformed_tag_exits_2(tmp_path: Path, tag: str) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(f"# Changelog\n\n## {tag}\n\nBody.\n", "utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "changelog_section.py"),
            tag,
            "--changelog",
            str(changelog),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "is not of the form" in result.stderr, result.stderr


def test_r922_a_post_release_tag_has_its_own_section() -> None:
    """R-922 (V03-post1): `vX.Y.Z.postN` reads its own heading, never X.Y.Z's, and X.Y.Z's tag
    never reads the post-release's."""
    changelog = (
        "# Changelog\n\n## v0.3.0.post1 — README only\n\nPost.\n\n"
        "## v0.3.0 — the release\n\nRelease.\n"
    )
    assert changelog_section.section(changelog, "v0.3.0.post1") == "Post.\n"
    assert changelog_section.section(changelog, "v0.3.0") == "Release.\n"
    with pytest.raises(changelog_section.MissingSectionError, match="0 sections"):
        changelog_section.section(changelog, "v0.3.0.post2")
    for malformed in ("v0.3.0.post0", "v0.3.0.post01", "v0.3.0rc1.post1", "v0.3.0post1"):
        with pytest.raises(ValueError, match="vX.Y.Z.postN"):
            changelog_section.section(changelog, malformed)
