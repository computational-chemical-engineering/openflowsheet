"""Shared fixtures for the repository test suite (P00 baseline, extended by P01)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The reason a test that reads the pre-0.1.0 development history skips where that history is not.
ARCHIVED_HISTORY = "pre-0.1.0 development history is archived in openflowsheet-dev (R-150)"
#: v0.1.0 on the public line: the root commit of `computational-chemical-engineering/openflowsheet`,
#: whose tree is the archive's v0.1.0 tree but which has none of its history (R-150).
PUBLIC_ROOT = "5a350199f1334e52cfd789109a0e1dc944ef328c"


def _git_ok(*arguments: str) -> bool:
    completed = subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True)
    return completed.returncode == 0


def require_archived_history(*commits: str, in_history_of_head: bool = False) -> None:
    """Skip the calling test unless each of `commits`, pre-0.1.0 commits the test reads, is in
    this repository (`git cat-file -e`) and, with `in_history_of_head`, an ancestor of `HEAD`.

    The development history up to v0.1.0 is archived in the private `openflowsheet-dev`; the
    public repository starts at `PUBLIC_ROOT` without it (R-150). A test that reads the log or a
    range of `HEAD` needs the commit in `HEAD`'s history, not only in the object store (a
    worktree of a development checkout holds the archive's objects beside the public line).
    Where the history is present, the test runs unchanged.
    """
    for commit in commits:
        present = _git_ok("cat-file", "-e", f"{commit}^{{commit}}")
        if not present or (
            in_history_of_head and not _git_ok("merge-base", "--is-ancestor", commit, "HEAD")
        ):
            pytest.skip(f"{ARCHIVED_HISTORY}: {commit} is not in this repository's history")


def in_public_root(path: Path) -> bool:
    """Whether `path` (under `REPO_ROOT`) is a file of v0.1.0 as `PUBLIC_ROOT` released it."""
    return _git_ok("cat-file", "-e", f"{PUBLIC_ROOT}:{path.relative_to(REPO_ROOT).as_posix()}")


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's exact bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> Any:
    """Load one YAML document with the safe loader."""
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root that contains docs/, schemas/, src/, benchmarks/ and evidence/."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def reference_values() -> dict[str, Any]:
    """Fable's 20-digit SYN-001 reference values, independent of the oracle implementation.

    Read-only. It is never regenerated from the oracle: doing so would turn an independent
    expectation into a self-generated regression fixture (CLAUDE.md, "Scientific conduct").
    """
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def registry() -> dict[str, Any]:
    """`benchmarks/registry.yaml`: the registered case semantics, tolerances and budgets."""
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    assert isinstance(loaded, dict)
    return loaded
