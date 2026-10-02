"""Shared fixtures for the repository test suite (P00 baseline, extended by P01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


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
