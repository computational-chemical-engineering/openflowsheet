"""P00 baseline: every committed evidence manifest is well formed and honest.

Validates each `evidence/<package>/<commit>/manifest.json` against
`schemas/evidence-manifest.schema.json`, rejects angle-bracket placeholder text anywhere in the
document, checks that the directory name matches the recorded `work_package` and `commit`, and
checks that the recorded commit is an object that actually exists in this repository.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def manifest_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "evidence").glob("*/*/manifest.json"))


def iter_strings(node: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, str):
        found.append((path, node))
    elif isinstance(node, dict):
        for key, value in node.items():
            found.extend(iter_strings(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(iter_strings(value, f"{path}[{index}]"))
    return found


@pytest.fixture(scope="session")
def manifest_schema(repo_root: Path) -> dict[str, Any]:
    with (repo_root / "schemas" / "evidence-manifest.schema.json").open(encoding="utf-8") as f:
        loaded = json.load(f)
    assert isinstance(loaded, dict)
    return loaded


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "manifest_path" in metafunc.fixturenames:
        root = Path(__file__).resolve().parent.parent
        paths = manifest_paths(root)
        metafunc.parametrize(
            "manifest_path",
            paths,
            ids=[str(p.relative_to(root)) for p in paths],
        )


def load(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert isinstance(loaded, dict), f"{manifest_path} is not a JSON object"
    return loaded


def test_schema_is_itself_valid(manifest_schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(manifest_schema)


def test_manifest_validates(manifest_path: Path, manifest_schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(manifest_schema).iter_errors(load(manifest_path)),
        key=lambda err: list(err.absolute_path),
    )
    assert not errors, "\n".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)


def test_manifest_has_no_angle_bracket_placeholders(manifest_path: Path) -> None:
    offenders = [
        f"{path}: {text}"
        for path, text in iter_strings(load(manifest_path))
        if ANGLE_PLACEHOLDER.search(text)
    ]
    assert not offenders, "angle-bracket placeholders are never valid evidence: " + "; ".join(
        offenders
    )


def test_manifest_path_matches_contents(manifest_path: Path) -> None:
    manifest = load(manifest_path)
    commit_dir = manifest_path.parent
    package_dir = commit_dir.parent
    assert package_dir.name == manifest["work_package"], (
        f"{manifest_path} sits under {package_dir.name} but records "
        f"work_package {manifest['work_package']}"
    )
    assert commit_dir.name == manifest["commit"], (
        f"{manifest_path} sits under {commit_dir.name} but records commit {manifest['commit']}"
    )


def test_manifest_commit_is_a_full_hash(manifest_path: Path) -> None:
    assert HEX40.match(load(manifest_path)["commit"])


def test_manifest_commit_exists_in_repository(manifest_path: Path, repo_root: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available; commit existence cannot be checked here")
    inside = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inside.returncode != 0:
        pytest.skip("not a git working tree; commit existence cannot be checked here")
    commit = load(manifest_path)["commit"]
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"commit {commit} recorded in {manifest_path} does not exist in this repository "
        f"({result.stderr.strip()})"
    )


def test_lead_model_did_not_self_certify_review(manifest_path: Path) -> None:
    """`reviewed` requires a named reviewer in both review fields, not `pending`."""
    manifest = load(manifest_path)
    if manifest["status"] in {"reviewed", "released"}:
        review = manifest["review"]
        assert review["numerical"] != "pending", manifest_path
        assert review["process_model"] != "pending", manifest_path
