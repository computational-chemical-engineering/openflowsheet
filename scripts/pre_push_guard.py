#!/usr/bin/env python3
"""Pre-push guard: no commit that does not descend from v0.1.0 reaches the public repository.

The public repository `computational-chemical-engineering/openflowsheet` starts at its root commit
`PUBLIC_ROOT` (v0.1.0); the development history before it is private, archived in
`openflowsheet-dev` (R-150). A clone that holds both lines — a development checkout with a
worktree of the public line, say — could publish the private history with one `git push`. This
hook refuses that.

Installed as the clone's `pre-push` hook by `scripts/install-hooks.sh` (a copy, so it does not
depend on the checked-out branch). Git runs it with the remote's name and URL as arguments and one
line per ref on standard input, `<local ref> <local object> <remote ref> <remote object>`. A push to
a URL naming `computational-chemical-engineering/openflowsheet…` (any letter case), except the
archive `…/openflowsheet-dev`, is refused unless every commit it could send — every commit
reachable from a pushed object and not from `PUBLIC_ROOT` — has `PUBLIC_ROOT` as an ancestor. A
deletion sends nothing and passes. Where `PUBLIC_ROOT` is not in the repository, or git fails,
nothing is shown to descend from it and the push is refused. Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

#: v0.1.0, the root commit of the public repository.
PUBLIC_ROOT: Final = "5a350199f1334e52cfd789109a0e1dc944ef328c"
#: The organization's repositories named `openflowsheet…`, read from a remote URL.
REPOSITORY: Final = re.compile(r"computational-chemical-engineering/(openflowsheet[^/\s]*)")
#: The private archive of the pre-0.1.0 history, the one such repository a push may reach freely.
ARCHIVE: Final = "openflowsheet-dev"
#: How many offending commits a refusal names.
SHOWN: Final = 5


class RefusalError(Exception):
    """The push would send commits that do not descend from `PUBLIC_ROOT`, or cannot be judged."""


def guarded(url: str) -> bool:
    """Whether `url` names a `computational-chemical-engineering/openflowsheet…` repository
    other than the archive."""
    names = [name.removesuffix(".git") for name in REPOSITORY.findall(url.lower())]
    return any(name != ARCHIVE for name in names)


def _git(cwd: Path, *arguments: str) -> list[str]:
    completed = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RefusalError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.split()


def foreign_commits(objects: Sequence[str], root: str, cwd: Path) -> list[str]:
    """The commits reachable from `objects` that are neither `root` nor its descendants."""
    if not objects:
        return []
    _git(cwd, "cat-file", "-e", f"{root}^{{commit}}")
    sent = _git(cwd, "rev-list", *objects, "--not", root)
    descendants = set(_git(cwd, "rev-list", "--ancestry-path", *objects, "--not", root))
    return [commit for commit in sent if commit not in descendants]


def pushed_objects(lines: Iterable[str]) -> list[str]:
    """The local objects of git's pre-push lines; a deletion (all zeros) pushes none."""
    objects: list[str] = []
    for line in lines:
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4:
            raise RefusalError(f"unreadable pre-push line {line.strip()!r}")
        if fields[1].strip("0"):
            objects.append(fields[1])
    return objects


def check(url: str, lines: Iterable[str], *, root: str = PUBLIC_ROOT, cwd: Path) -> None:
    """Raise `RefusalError` unless the push of `lines` to `url` is allowed."""
    if not guarded(url):
        return
    try:
        foreign = foreign_commits(pushed_objects(lines), root, cwd)
    except RefusalError as error:
        raise RefusalError(
            f"{error}; cannot show that the push descends from {root[:12]}"
        ) from None
    if foreign:
        shown = ", ".join(commit[:12] for commit in foreign[:SHOWN])
        more = f" and {len(foreign) - SHOWN} more" if len(foreign) > SHOWN else ""
        raise RefusalError(
            f"{len(foreign)} commits do not descend from v0.1.0 ({root[:12]}): {shown}{more}. "
            "The pre-0.1.0 history is private (R-150)"
        )


def main(argv: Sequence[str]) -> int:
    url = argv[1] if len(argv) > 1 else ""
    try:
        check(url, sys.stdin, cwd=Path.cwd())
    except RefusalError as error:
        print(f"pre-push: refused push to {url}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
