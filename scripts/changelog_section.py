"""Print the `CHANGELOG.md` section of a release tag: the GitHub release notes of `release.yml`.

The section of `vX.Y.Z` is the text under the level-2 heading that begins `## vX.Y.Z` (followed by
the end of the line or a space), up to the next level-2 heading or the end of the file, without
the heading itself and stripped of surrounding blank lines. Exit 1 if the changelog has no such
heading, more than one, or an empty section; exit 2 if the tag is not of the form `vX.Y.Z`.

    python scripts/changelog_section.py v0.1.0 > notes.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
TAG: Final = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


class MissingSectionError(Exception):
    """The changelog has no single, non-empty section for the tag."""


def section(changelog: str, tag: str) -> str:
    """The body of `tag`'s section of `changelog`."""
    if TAG.fullmatch(tag) is None:
        raise ValueError(f"tag {tag!r} is not of the form vX.Y.Z")
    heading = re.compile(rf"## {re.escape(tag)}(?:\s.*)?")
    lines = changelog.splitlines()
    starts = [n for n, line in enumerate(lines) if heading.fullmatch(line)]
    if len(starts) != 1:
        raise MissingSectionError(f"CHANGELOG.md has {len(starts)} sections headed `## {tag}`")
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    text = "\n".join(body).strip("\n")
    if not text.strip():
        raise MissingSectionError(f"CHANGELOG.md's section `## {tag}` is empty")
    return text + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="the release tag, vX.Y.Z")
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    arguments = parser.parse_args()
    try:
        print(section(arguments.changelog.read_text(encoding="utf-8"), arguments.tag), end="")
    except ValueError as error:
        parser.error(str(error))
    except MissingSectionError as missing:
        print(f"error: {missing}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
