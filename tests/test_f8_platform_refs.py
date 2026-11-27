"""F8-WO5: per-platform reference records, ADR 0067 D7 (exit E-F8-8).

The synthetic case is a reference record made from GP-C1's artifacts (F8-WO2's factory), and a
`linux-aarch64` record in which one float is moved beyond the numerical policy.

Mutation controls (run by hand, not committed; each makes the named tests fail):
- selection: `select_reference` ignores the per-platform record (`test_selection_*`,
  `test_fake_platform_*`);
- invariant: `invariant_problems` skips the R0 comparison (`test_invariant_reports_changed_r0`),
  or the `reference_sha256` comparison (`test_invariant_reports_stale_reference_sha`);
- refusals: `load_platform_record` skips its self-hash check (`test_refusal_bad_self_hash`),
  its file-name check (`test_refusal_file_name_not_the_case`) or its departure value checks
  (`test_refusal_malformed_departure`); `invariant_problems` skips the missing-reference guard
  (`test_invariant_reports_a_missing_reference_record`).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from f8_bundle_v2_support import legacy_stack, record_v2

from openflowsheet.application.revision_replay import declared_kinds
from openflowsheet.application.revision_run import select_route
from openflowsheet.run import platform_refs, replay
from openflowsheet.run.compare import CURRENT_POLICY_ID, V1_POLICY_ID, differences
from openflowsheet.run.platform_refs import (
    PLATFORM_IDS,
    REFERENCE_PLATFORM,
    all_cases,
    compare_to_reference,
    current_platform,
    invariant_problems,
    load_platform_record,
    platform_record_path,
    record_sha256,
    registered_platform_ids,
    select_reference,
    self_sha256,
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402

AARCH64 = "linux-aarch64"
CASE = "GP-C1"


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    with gate.pinned_threads():
        recorded = record_v2("s11-gp", CASE, tmp_path_factory.mktemp("case"), legacy_stack())
    return dict(recorded.artifacts)


def _first_float(node: Any, path: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
    if isinstance(node, float) and node != 0.0:
        return path
    if isinstance(node, dict):
        children = list(node.items())
    elif isinstance(node, list):
        children = list(enumerate(node))
    else:
        return None
    for key, child in children:
        found = _first_float(child, (*path, key))
        if found is not None:
            return found
    return None


def _moved(artifacts: dict[str, Any]) -> tuple[dict[str, Any], str, float, float]:
    """A copy of the artifacts with one float of the solution state doubled and shifted."""
    moved = copy.deepcopy(artifacts)
    path = _first_float(moved["solution-state.json"])
    assert path is not None
    parent = moved["solution-state.json"]
    for key in path[:-1]:
        parent = parent[key]
    before = parent[path[-1]]
    parent[path[-1]] = 2.0 * before + 1.0
    return moved, "solution-state.json/" + "/".join(map(str, path)), before, parent[path[-1]]


def _write(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def _departure(case_path: Path) -> dict[str, Any]:
    """The one departure row of the case's `linux-aarch64` record."""
    record = json.loads(platform_record_path(case_path, AARCH64).read_text(encoding="utf-8"))
    row: dict[str, Any] = record["departures"][0]
    return row


def _platform_document(
    case_path: Path,
    artifacts: dict[str, Any],
    platform_id: str,
    row: tuple[str, float, float],
) -> dict[str, Any]:
    path, reference_value, platform_value = row
    bound = 1e-9 * abs(reference_value)
    document: dict[str, Any] = {
        "platform_reference_format": platform_refs.FORMAT,
        "case": CASE,
        "platform": platform_id,
        "reference_platform": REFERENCE_PLATFORM,
        "reference_sha256": record_sha256(json.loads(case_path.read_text(encoding="utf-8"))),
        "departures": [
            {
                "path": path,
                "reference_value": reference_value,
                "platform_value": platform_value,
                "bound": bound,
                "ratio": abs(platform_value - reference_value) / bound,
                "near_threshold": False,
            }
        ],
        "artifacts": artifacts,
    }
    document["self_sha256"] = self_sha256(document)
    return document


@pytest.fixture
def case(tmp_path: Path, artifacts: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """A reference record, a `linux-aarch64` record beside it, and the moved artifacts."""
    case_path = tmp_path / f"{CASE}.json"
    _write(case_path, {"case": CASE, "artifacts": artifacts})
    moved, path, before, after = _moved(artifacts)
    document = _platform_document(case_path, moved, AARCH64, (path, before, after))
    _write(platform_record_path(case_path, AARCH64), document)
    return case_path, moved


# --- platform ids ----------------------------------------------------------------------------


def test_platform_ids_and_registered_set() -> None:
    assert PLATFORM_IDS == {
        ("x86_64", "Linux"): "linux-x86_64",
        ("aarch64", "Linux"): "linux-aarch64",
        ("arm64", "Darwin"): "macos-arm64",
        ("AMD64", "Windows"): "windows-x86_64",
    }
    assert registered_platform_ids() == {"linux-x86_64", "linux-aarch64"}
    assert current_platform() in set(PLATFORM_IDS.values()) | {None}


def test_platform_record_path() -> None:
    assert platform_record_path(Path("d/GP-C1.json"), AARCH64) == Path("d/GP-C1.linux-aarch64.json")


# --- E-F8-8 selection --------------------------------------------------------------------------


def test_selection_per_platform_record_is_used(case: tuple[Path, dict[str, Any]]) -> None:
    case_path, moved = case
    found, notices = compare_to_reference(case_path, moved, AARCH64, policy_id=V1_POLICY_ID)
    assert found == []
    assert [(n.code, dict(n.params)) for n in notices] == [
        ("platform_reference_used", {"platform": AARCH64})
    ]
    _, used = select_reference(case_path, AARCH64)
    assert used == AARCH64


def test_selection_reference_platform_uses_the_reference(
    case: tuple[Path, dict[str, Any]],
) -> None:
    case_path, moved = case
    reference = platform_refs.record_artifacts(json.loads(case_path.read_text(encoding="utf-8")))
    assert compare_to_reference(
        case_path, dict(reference), REFERENCE_PLATFORM, policy_id=V1_POLICY_ID
    ) == ([], []), "control: the reference agrees with itself"
    found, notices = compare_to_reference(
        case_path, moved, REFERENCE_PLATFORM, policy_id=V1_POLICY_ID
    )
    row = _departure(case_path)
    # The one difference is the moved float, at its path, with its value.
    assert len(found) == 1, found
    assert row["path"].replace("/", ".") in found[0] and repr(row["platform_value"]) in found[0]
    assert notices == []
    assert select_reference(case_path, REFERENCE_PLATFORM)[1] is None


def test_selection_other_platform_without_record_uses_the_reference(
    case: tuple[Path, dict[str, Any]],
) -> None:
    case_path, moved = case
    found, notices = compare_to_reference(case_path, moved, "macos-arm64", policy_id=V1_POLICY_ID)
    assert len(found) == 1 and notices == []


def test_selection_under_the_v2_policy(case: tuple[Path, dict[str, Any]]) -> None:
    """The same selection under `T08-numerical-policy-v2`, with the route's declared kinds (as
    RC step 5 compares, `f8_bundle_v2_support.rerun_v2`)."""
    case_path, moved = case
    reference = platform_refs.record_artifacts(json.loads(case_path.read_text(encoding="utf-8")))
    route = select_route(reference["revision.json"])
    kinds = declared_kinds(route.binding.spec)  # type: ignore[union-attr]
    assert kinds
    found, notices = compare_to_reference(
        case_path, moved, AARCH64, policy_id=CURRENT_POLICY_ID, variable_kinds=kinds
    )
    assert found == []
    assert [(n.code, dict(n.params)) for n in notices] == [
        ("platform_reference_used", {"platform": AARCH64})
    ]
    found, notices = compare_to_reference(
        case_path, moved, REFERENCE_PLATFORM, policy_id=CURRENT_POLICY_ID, variable_kinds=kinds
    )
    assert len(found) == 1 and CURRENT_POLICY_ID in found[0] and notices == []


def test_fake_platform_uses_its_record(
    case: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    case_path, moved = case
    monkeypatch.setitem(PLATFORM_IDS, ("fake", "Fakeos"), "fake-arch")
    monkeypatch.setattr(
        replay, "REGISTERED_PLATFORMS", replay.REGISTERED_PLATFORMS | {("fake", "Fakeos")}
    )
    assert "fake-arch" in registered_platform_ids()
    # Before the fake platform has a record of its own, it is compared with the reference.
    found, notices = compare_to_reference(case_path, moved, "fake-arch", policy_id=V1_POLICY_ID)
    assert len(found) == 1 and notices == []
    document = json.loads(platform_record_path(case_path, AARCH64).read_text(encoding="utf-8"))
    document["platform"] = "fake-arch"
    document["self_sha256"] = self_sha256(document)
    _write(platform_record_path(case_path, "fake-arch"), document)

    reference = platform_refs.record_artifacts(json.loads(case_path.read_text(encoding="utf-8")))
    assert len(differences(moved, reference, policy_id=V1_POLICY_ID)) == 1
    found, notices = compare_to_reference(case_path, moved, "fake-arch", policy_id=V1_POLICY_ID)
    assert found == []
    assert [(n.code, dict(n.params)) for n in notices] == [
        ("platform_reference_used", {"platform": "fake-arch"})
    ]


# --- E-F8-8 invariant --------------------------------------------------------------------------


def test_invariant_holds_over_the_repository() -> None:
    roots = [REPO_ROOT / name for name in ("tests/fixtures", "benchmarks", "corpus")]
    cases = all_cases(roots)
    problems = [problem for path in cases for problem in invariant_problems(path)]
    print(f"per-platform reference records found: {len(cases)} case(s)")
    assert problems == []


def test_invariant_synthetic_case_is_clean(case: tuple[Path, dict[str, Any]]) -> None:
    case_path, _ = case
    assert all_cases([case_path.parent]) == [case_path]
    assert invariant_problems(case_path) == []


def _rename_inner_row(artifacts: dict[str, Any]) -> None:
    artifacts["solve-plan.json"]["inner_row_ids"][0] += "x"


def _count_one_more_residual(artifacts: dict[str, Any]) -> None:
    # The last event's: the projection carries the final cumulative counters (F8-WO5-R3).
    artifacts["solve-events.json"][-1]["counters"]["residual_calls"] += 1


@pytest.mark.parametrize("change", [_rename_inner_row, _count_one_more_residual])
def test_invariant_reports_changed_r0(case: tuple[Path, dict[str, Any]], change: Any) -> None:
    case_path, _ = case
    path = platform_record_path(case_path, AARCH64)
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document["artifacts"])
    document["self_sha256"] = self_sha256(document)
    _write(path, document)
    problems = invariant_problems(case_path)
    assert len(problems) == 1 and "R0 projection differs" in problems[0]


def test_invariant_reports_a_missing_reference_record(case: tuple[Path, dict[str, Any]]) -> None:
    case_path, _ = case
    case_path.unlink()
    assert all_cases([case_path.parent]) == [case_path]
    problems = invariant_problems(case_path)
    assert len(problems) == 1 and "without their reference record" in problems[0]


def test_invariant_reports_stale_reference_sha(case: tuple[Path, dict[str, Any]]) -> None:
    case_path, _ = case
    document = json.loads(case_path.read_text(encoding="utf-8"))
    document["case"] = "renamed"
    _write(case_path, document)
    problems = invariant_problems(case_path)
    assert len(problems) == 1 and "reference_sha256" in problems[0]


# --- refusals (spec 4) -------------------------------------------------------------------------


def _edited(case: tuple[Path, dict[str, Any]], edit: Any, *, rehash: bool = True) -> Path:
    case_path, _ = case
    path = platform_record_path(case_path, AARCH64)
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    if rehash:
        document["self_sha256"] = self_sha256(document)
    _write(path, document)
    return path


def test_load_accepts_the_synthetic_record(case: tuple[Path, dict[str, Any]]) -> None:
    case_path, _ = case
    assert load_platform_record(platform_record_path(case_path, AARCH64))["platform"] == AARCH64


def test_refusal_wrong_format(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d.update(platform_reference_format="other"))
    with pytest.raises(ValueError, match="wrong format"):
        load_platform_record(path)


def test_load_ignores_line_endings_and_layout(case: tuple[Path, dict[str, Any]]) -> None:
    """ADR 0060 D3: the self-hash is over canonical JSON, so an indented CRLF file loads."""
    case_path, _ = case
    path = platform_record_path(case_path, AARCH64)
    document = json.loads(path.read_text(encoding="utf-8"))
    path.write_bytes(json.dumps(document, indent=2).replace("\n", "\r\n").encode("utf-8"))
    assert b"\r\n" in path.read_bytes()
    assert load_platform_record(path) == document


@pytest.mark.parametrize("unregistered", ["macos-arm64", "solaris-sparc"])
def test_refusal_unregistered_platform(
    case: tuple[Path, dict[str, Any]], unregistered: str
) -> None:
    path = _edited(case, lambda d: d.update(platform=unregistered))
    with pytest.raises(ValueError, match="unregistered platform"):
        load_platform_record(path)


def test_refusal_reference_platform(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d.update(platform=REFERENCE_PLATFORM))
    with pytest.raises(ValueError, match="reference platform"):
        load_platform_record(path)


def test_refusal_bad_self_hash(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d.update(case="other"), rehash=False)
    with pytest.raises(ValueError, match="bad self_sha256"):
        load_platform_record(path)


def test_refusal_file_name_not_the_case(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d.update(case="GP-C2"))
    with pytest.raises(ValueError, match="must be named"):
        load_platform_record(path)


@pytest.mark.parametrize(
    ("member", "value", "rule"),
    [
        ("bound", 0.0, "bound positive"),
        ("platform_value", "1.0", "must be numbers"),
        ("reference_value", None, "must be numbers"),
        ("near_threshold", 0, "near_threshold must be a boolean"),
    ],
)
def test_refusal_malformed_departure(
    case: tuple[Path, dict[str, Any]], member: str, value: Any, rule: str
) -> None:
    path = _edited(case, lambda d: d["departures"][0].update({member: value}))
    with pytest.raises(ValueError, match=rule):
        load_platform_record(path)


def test_refusal_empty_departures(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d.update(departures=[]))
    with pytest.raises(ValueError, match="non-empty"):
        load_platform_record(path)


def test_refusal_unsorted_departures(case: tuple[Path, dict[str, Any]]) -> None:
    def edit(document: dict[str, Any]) -> None:
        first = document["departures"][0]
        second = {**first, "path": "a/" + first["path"]}
        document["departures"] = [first, second]

    path = _edited(case, edit)
    with pytest.raises(ValueError, match="sorted by path"):
        load_platform_record(path)


def test_refusal_ratio_not_above_one(case: tuple[Path, dict[str, Any]]) -> None:
    def edit(document: dict[str, Any]) -> None:
        row = document["departures"][0]
        row["bound"] = 10.0 * abs(row["platform_value"] - row["reference_value"])
        row["ratio"] = 0.1

    path = _edited(case, edit)
    with pytest.raises(ValueError, match="must exceed 1"):
        load_platform_record(path)


def test_refusal_ratio_not_the_formula(case: tuple[Path, dict[str, Any]]) -> None:
    path = _edited(case, lambda d: d["departures"][0].update(ratio=d["departures"][0]["ratio"] * 2))
    with pytest.raises(ValueError, match="is not"):
        load_platform_record(path)
