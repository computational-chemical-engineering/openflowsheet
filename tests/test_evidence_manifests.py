"""P00 baseline: every committed evidence manifest is well formed and honest.

Validates each `evidence/<package>/<commit>/manifest.json` against
`schemas/evidence-manifest.schema.json`, rejects angle-bracket placeholder text anywhere in the
document, checks that the directory name matches the recorded `work_package` and `commit`, and
checks that the recorded commit is an object that actually exists in this repository.
"""

from __future__ import annotations

import itertools
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import in_public_root, require_archived_history
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


def test_work_package_pattern_widening_is_additive(manifest_schema: dict[str, Any]) -> None:
    """ADR 0059 D1: every id the old pattern accepted still matches; the roadmap's ids are admitted
    and R-565's refusals stand."""
    pattern = re.compile(manifest_schema["properties"]["work_package"]["pattern"])
    old = re.compile(r"^[PKTMSR][0-9]{2}[a-z]?$")
    suffixes = ["", *"abcdefghijklmnopqrstuvwxyz"]
    ids = [f"{letter}{n:02d}{s}" for letter in "PKTMSR" for n in range(100) for s in suffixes]
    assert len(ids) == 6 * 100 * 27 and all(old.match(i) for i in ids)
    assert all(pattern.match(i) for i in ids)
    for admitted in ("F0", "F9", "X07a", "X26", "TX", "MSG", "ST", "OPT", "RRC", "PrISMa"):
        assert pattern.match(admitted), admitted
    for refused in ("L01", "C9", "E01", "V03", "W1", "FB-04", "f0", "F10", "FO", "MGS", "", "<id>"):
        assert not pattern.match(refused), refused


ADR0059_PATTERN = r"^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa)$"
REL_ALTERNATIVE = "|REL(?:[0-9]|b[1-9][0-9]|c[1-9][0-9]{2}|d[1-9][0-9]{3}){3}"
RID_SET = (0, 1, 2, 9, 10, 11, 99, 100, 101, 999, 1000, 1001, 9999)


def rel_code(n: int) -> str:
    """ADR 0074 D2: the digit below 10, else the k-th lower-case letter and the k digits."""
    digits = str(n)
    return digits if n < 10 else chr(ord("a") + len(digits) - 1) + digits


def rel_id(x: int, y: int, z: int) -> str:
    return "REL" + rel_code(x) + rel_code(y) + rel_code(z)


def rel_pattern(manifest_schema: dict[str, Any]) -> re.Pattern[str]:
    return re.compile(manifest_schema["properties"]["work_package"]["pattern"])


def test_rid_a01_pattern_is_one_alternative_added(manifest_schema: dict[str, Any]) -> None:
    """ADR 0074 RID.A01: ADR 0059 D1's string with exactly the REL alternative before `)$`."""
    expected = ADR0059_PATTERN[: -len(")$")] + REL_ALTERNATIVE + ")$"
    assert manifest_schema["properties"]["work_package"]["pattern"] == expected


REL_REGISTERED = [
    ((0, 0, 0), "REL000"),
    ((0, 1, 10), "REL01b10"),
    ((0, 4, 0), "REL040"),
    ((0, 4, 1), "REL041"),
    ((0, 5, 0), "REL050"),
    ((0, 9, 9), "REL099"),
    ((0, 10, 0), "REL0b100"),
    ((0, 11, 0), "REL0b110"),
    ((0, 99, 0), "REL0b990"),
    ((0, 100, 0), "REL0c1000"),
    ((1, 0, 0), "REL100"),
    ((1, 1, 10), "REL11b10"),
    ((1, 10, 0), "REL1b100"),
    ((1, 11, 0), "REL1b110"),
    ((9, 9, 9), "REL999"),
    ((10, 10, 10), "RELb10b10b10"),
    ((11, 0, 0), "RELb1100"),
    ((11, 1, 0), "RELb1110"),
    ((2027, 1, 0), "RELd202710"),
    ((9999, 9999, 9999), "RELd9999d9999d9999"),
]

REL_REFUSED = [
    "REL", "REL04", "REL0400", "REL1100", "REL0110", "REL1110", "REL0100", "REL01000",
    "REL0b010", "REL0b5", "REL0b1000", "REL0c100", "REL0c0100", "REL0a40", "REL0B100",
    "REL0b10b10b10", "REL0e100000", "RELe1000000", "rel040", "Rel040", "REL040a", "REL-040",
    "REL_040", "REL.040", "REL0.4.0", "REL.A01", "REL040 ", " REL040", "RELL040", "RE040",
    "REL\u0660\u0664\u0660", "REL04\u00b9",
]  # fmt: skip


def test_rid_a03_old_pattern_refuses_every_release_id() -> None:
    """RID.A03: ADR 0059 D1's literal pattern admits none of the registered or S^3 ids."""
    old = re.compile(ADR0059_PATTERN)
    ids = [i for _, i in REL_REGISTERED]
    ids += [rel_id(x, y, z) for x in RID_SET for y in RID_SET for z in RID_SET]
    assert not any(old.search(i) for i in ids)


@pytest.mark.parametrize(("version", "expected"), REL_REGISTERED)
def test_rid_a04_registered_ids(
    version: tuple[int, int, int], expected: str, manifest_schema: dict[str, Any]
) -> None:
    assert rel_id(*version) == expected
    assert rel_pattern(manifest_schema).search(expected)


def test_rid_a04_table_is_in_version_and_code_point_order() -> None:
    assert [v for v, _ in REL_REGISTERED] == sorted(v for v, _ in REL_REGISTERED)
    ids = [i for _, i in REL_REGISTERED]
    assert ids == sorted(ids)


def test_rid_a05_refused_strings(manifest_schema: dict[str, Any]) -> None:
    assert len(REL_REFUSED) == 32 and len(set(REL_REFUSED)) == 32
    pattern = rel_pattern(manifest_schema)
    accepted = [s for s in REL_REFUSED if pattern.search(s)]
    assert not accepted, accepted


def test_rid_a06_exact_language_on_a_window(manifest_schema: dict[str, Any]) -> None:
    """RID.A06: over all strings of length <= 5 on `0123456789abcde`, the pattern accepts
    `REL`+s exactly when s is code(X)code(Y)code(Z); 28 000 of the 813 616 are accepted."""
    alphabet = "0123456789abcde"
    pattern = rel_pattern(manifest_schema)
    valid = {
        rel_code(x) + rel_code(y) + rel_code(z)
        for x in range(100)
        for y in range(100)
        for z in range(100)
    }
    valid = {s for s in valid if len(s) <= 5}
    total = accepted = 0
    for length in range(6):
        for chars in itertools.product(alphabet, repeat=length):
            s = "".join(chars)
            total += 1
            hit = pattern.search("REL" + s) is not None
            assert hit == (s in valid), s
            accepted += hit
    assert total == 813_616
    assert accepted == 28_000


def test_rid_a07_range_every_marker_every_position(manifest_schema: dict[str, Any]) -> None:
    """RID.A07: 30 300 checks, 30 000 accepted and 300 refused (x > 9 999, D3)."""
    pattern = rel_pattern(manifest_schema)
    accepted = refused = 0
    for x in range(10_100):
        for version in ((x, 0, 0), (0, x, 0), (0, 0, x)):
            hit = pattern.search(rel_id(*version)) is not None
            assert hit == (x <= 9_999), version
            accepted += hit
            refused += not hit
    assert (accepted, refused) == (30_000, 300)


def rid_versions() -> list[tuple[int, int, int]]:
    return [(x, y, z) for x in RID_SET for y in RID_SET for z in RID_SET]


def test_rid_a08_injective_prefix_free_case_unique_ordered() -> None:
    versions = rid_versions()
    assert versions == sorted(versions) and len(versions) == 13**3 == 2_197
    ids = [rel_id(*v) for v in versions]
    assert len(set(ids)) == 2_197
    assert len({i.lower() for i in ids}) == 2_197
    assert all(not b.startswith(a) for a, b in zip(ids, ids[1:], strict=False))
    assert sorted(ids) == ids


def test_rid_a09_plain_digit_forms_settled(manifest_schema: dict[str, Any]) -> None:
    """RID.A09: N-4 in both halves."""
    pattern = rel_pattern(manifest_schema)
    big = small = 0
    for v in rid_versions():
        plain = "REL" + "".join(str(c) for c in v)
        if max(v) >= 10:
            big += 1
            assert not pattern.search(plain), plain
        else:
            small += 1
            assert plain == rel_id(*v), plain
    assert (big, small) == (13**3 - 4**3, 4**3) == (2_133, 64)


def test_rid_a10_line_schema_admits_every_id(repo_root: Path) -> None:
    """RID.A10: the line-file `gate_set.evidence_package` pattern needs no widening."""
    line_schema = json.loads(
        (repo_root / "release" / "lines" / "release-line-v1.schema.json").read_text("utf-8")
    )
    patterns: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "evidence_package" in node.get("properties", {}):
                patterns.append(node["properties"]["evidence_package"]["pattern"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(line_schema)
    assert len(patterns) == 1, patterns
    line = re.compile(patterns[0])
    assert all(line.search(rel_id(*v)) for v in rid_versions())


def test_rid_a11_through_the_validator(manifest_schema: dict[str, Any]) -> None:
    """RID.A11: REL040 and RELb1100 validate; the plain form REL1100 does not."""
    validator = Draft202012Validator(manifest_schema["properties"]["work_package"])
    assert validator.is_valid("REL040") and validator.is_valid("RELb1100")
    assert not validator.is_valid("REL1100")


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
    if in_public_root(manifest_path):
        # A manifest released in v0.1.0 cites a commit of the archived history (R-150); a
        # manifest written since must cite a commit of this repository.
        require_archived_history(commit)
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
