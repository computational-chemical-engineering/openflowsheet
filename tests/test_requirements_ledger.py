"""P00 baseline: `docs/requirements.yaml` is a usable traceability ledger.

Checks that the ledger validates against its JSON Schema, that the document hashes it records
are the actual hashes (and agree with the plan header), that every package ID it references
exists in its own `packages` table, and that no field carries an angle-bracket placeholder.
Angle-bracket text in the plan's templates is a schema example, never valid ledger content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import sha256_of
from jsonschema import Draft202012Validator

ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")


@pytest.fixture(scope="session")
def ledger(repo_root: Path) -> dict[str, Any]:
    with (repo_root / "docs" / "requirements.yaml").open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def ledger_schema(repo_root: Path) -> dict[str, Any]:
    with (repo_root / "schemas" / "requirements-ledger.schema.json").open(encoding="utf-8") as f:
        loaded = json.load(f)
    assert isinstance(loaded, dict)
    return loaded


def iter_strings(node: Any, path: str = "$") -> list[tuple[str, str]]:
    """Yield every (json-path, string) pair reachable in a decoded YAML/JSON document."""
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


def test_schema_is_itself_valid(ledger_schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(ledger_schema)


def test_ledger_validates(ledger: dict[str, Any], ledger_schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(ledger_schema).iter_errors(ledger),
        key=lambda err: list(err.absolute_path),
    )
    assert not errors, "\n".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)


def test_recorded_blueprint_hash_is_the_actual_file_hash(
    ledger: dict[str, Any], repo_root: Path
) -> None:
    recorded = ledger["blueprint"]["sha256"]
    actual = sha256_of(repo_root / ledger["blueprint"]["path"])
    assert recorded == actual


def test_recorded_blueprint_hash_matches_plan_header(
    ledger: dict[str, Any], repo_root: Path
) -> None:
    plan_text = (repo_root / ledger["plan"]["path"]).read_text(encoding="utf-8")
    match = re.search(r"^\*\*Baseline SHA-256:\*\*\s*`([0-9a-f]{64})`\s*$", plan_text, re.MULTILINE)
    assert match is not None, "implementation plan header has no `Baseline SHA-256:` line"
    assert ledger["blueprint"]["sha256"] == match.group(1)


def test_recorded_plan_hash_is_the_actual_file_hash(
    ledger: dict[str, Any], repo_root: Path
) -> None:
    assert ledger["plan"]["sha256"] == sha256_of(repo_root / ledger["plan"]["path"])


def test_package_ids_are_unique(ledger: dict[str, Any]) -> None:
    ids = [package["id"] for package in ledger["packages"]]
    assert len(ids) == len(set(ids)), "duplicate package IDs"


def test_requirement_and_gate_ids_are_unique(ledger: dict[str, Any]) -> None:
    requirement_ids = [item["id"] for item in ledger["requirements"]]
    gate_ids = [item["id"] for item in ledger["gates"]]
    assert len(requirement_ids) == len(set(requirement_ids)), "duplicate requirement IDs"
    assert len(gate_ids) == len(set(gate_ids)), "duplicate gate IDs"


def test_every_referenced_package_exists(ledger: dict[str, Any]) -> None:
    known = {package["id"] for package in ledger["packages"]}
    missing: list[str] = []
    for requirement in ledger["requirements"]:
        missing += [
            f"requirement {requirement['id']} -> {pkg}"
            for pkg in requirement["packages"]
            if pkg not in known
        ]
    for gate in ledger["gates"]:
        missing += [
            f"gate {gate['id']} -> {pkg}" for pkg in gate["owner_packages"] if pkg not in known
        ]
    for package in ledger["packages"]:
        missing += [
            f"package {package['id']} depends_on {dep}"
            for dep in package["depends_on"]
            if dep not in known
        ]
    assert not missing, "unknown package references: " + ", ".join(missing)


def test_package_dependencies_are_acyclic(ledger: dict[str, Any]) -> None:
    depends = {package["id"]: list(package["depends_on"]) for package in ledger["packages"]}
    resolved: set[str] = set()
    remaining = dict(depends)
    while remaining:
        ready = [pid for pid, deps in remaining.items() if set(deps) <= resolved]
        assert ready, f"cyclic or unresolvable dependencies among {sorted(remaining)}"
        resolved.update(ready)
        for pid in ready:
            del remaining[pid]


def test_statuses_use_the_declared_vocabulary(ledger: dict[str, Any]) -> None:
    vocabulary = set(ledger["status_vocabulary"])
    for package in ledger["packages"]:
        assert package["status"] in vocabulary, package["id"]
    for requirement in ledger["requirements"]:
        assert requirement["status"] in vocabulary, requirement["id"]


def test_every_blueprint_requirement_is_covered(ledger: dict[str, Any]) -> None:
    expected = {f"D{n:02d}" for n in range(1, 21)} | {f"A{n:02d}" for n in range(1, 11)}
    assert {item["id"] for item in ledger["requirements"]} == expected


def test_every_release_gate_is_covered(ledger: dict[str, Any]) -> None:
    expected = (
        {f"G{n:02d}" for n in range(0, 7)}
        | {f"V{n}" for n in range(11, 21)}
        | {f"W{n}" for n in range(21, 28)}
        | {"X31", "X41", "X42"}
    )
    assert {item["id"] for item in ledger["gates"]} == expected


def test_no_angle_bracket_placeholders(ledger: dict[str, Any]) -> None:
    offenders = [
        f"{path}: {text}" for path, text in iter_strings(ledger) if ANGLE_PLACEHOLDER.search(text)
    ]
    assert not offenders, "angle-bracket placeholders are never valid values: " + "; ".join(
        offenders
    )


def test_every_cited_evidence_manifest_exists_and_says_what_is_claimed(
    ledger: dict[str, Any], repo_root: Path
) -> None:
    """A traceability pointer nobody follows is a claim, not a trace.

    The ledger's whole purpose is requirement -> test -> evidence, and until this test existed a
    mistyped commit hash or a manifest that was never written would have read exactly like a
    satisfied requirement. Each cited manifest must exist, be for the package that cites it, and
    carry the requirement whose row cites it.
    """
    problems: list[str] = []
    for requirement in ledger["requirements"]:
        for reference in requirement["evidence"]:
            path = repo_root / reference
            if not path.is_file():
                problems.append(
                    f"{requirement['id']} cites a manifest that does not exist: {reference}"
                )
                continue
            manifest = json.loads(path.read_text(encoding="utf-8"))
            package = reference.split("/")[1]
            if manifest.get("work_package") != package:
                problems.append(
                    f"{requirement['id']} cites {reference}, whose work_package is "
                    f"{manifest.get('work_package')!r} and not {package!r}"
                )
            if requirement["id"] not in manifest.get("requirements", []):
                problems.append(
                    f"{requirement['id']} cites {reference}, which does not list it among "
                    f"{manifest.get('requirements')}"
                )
            # The progression is planned -> implemented -> tested -> reviewed -> released and
            # it is one-directional, so anything from `implemented` on is evidence. The first
            # version of this listed only `implemented` and `tested`, which rejected the two
            # *stronger* statuses — caught the day a human signed the manifests off.
            if manifest.get("status") not in (
                "implemented",
                "tested",
                "reviewed",
                "released",
            ):
                problems.append(
                    f"{requirement['id']} cites {reference} with status "
                    f"{manifest.get('status')!r}; BLOCKED and planned are not evidence"
                )
    assert not problems, "\n".join(problems)


def test_every_cited_test_exists(ledger: dict[str, Any], repo_root: Path) -> None:
    """A cited node ID that pytest cannot collect traces a requirement to nothing.

    Node IDs are checked by reading the file rather than by collecting, so this stays a cheap
    unit test: a `path::name` must name a `def name` in that file, and a bare path must be a
    file. Parametrized IDs are matched on their stem.
    """
    missing: list[str] = []
    for requirement in ledger["requirements"]:
        for node in requirement["tests"]:
            relative, _, name = node.partition("::")
            path = repo_root / relative
            if not path.is_file():
                missing.append(f"{requirement['id']} -> {node} (no such file)")
                continue
            if name and f"def {name.partition('[')[0]}(" not in path.read_text(encoding="utf-8"):
                missing.append(f"{requirement['id']} -> {node} (no such test)")
    assert not missing, "cited tests that do not exist:\n" + "\n".join(missing)
