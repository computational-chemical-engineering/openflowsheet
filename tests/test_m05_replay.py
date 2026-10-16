"""G10's comparator and referent check in test support (`tests/support/m05_replay.py`; design note
§9.3, §19.1, §19.4; register R-384, R-385), on hand-built records: the coupling digests compared
for shape and their check ids exactly, every other float bitwise, `wall_s` excluded and positive;
the persisted coupling records' integrity (one file per coupled run, its sha256 the recorded
digest) and content (M02's `excluded` paths removed, floats by `float.hex`).

Default gate: no Pyomo, nothing runs.
"""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.canonical import canonical_json, document_sha256

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_replay as replay  # noqa: E402

COUPLING: dict[str, Any] = {
    "coupling_block": {"tau_xi_rel": 1e-6},
    "iterations": [
        {
            "w": [0.1, 12.5],
            "units": {
                "reactor": {
                    "xi_E": 0.25,
                    "attempts": [
                        {"execution": {"timing": {"wall_s": 0.0123, "started": 17.5}, "n": 1}}
                    ],
                }
            },
        }
    ],
}


def _record() -> dict[str, Any]:
    digest = document_sha256(COUPLING)
    return {
        "start": {"coupling_record_sha256": digest, "wall_s": 0.5, "objective": 1.25},
        "candidates": [
            {"solves": [{"coupling_record_sha256": None, "wall_s": 0.25, "objective": 1.5}]}
        ],
        "artifacts": {"coupled_runs": [{"check_id": "S0", "sha256": digest}]},
    }


def _set(record: Any, path: tuple[Any, ...], value: Any) -> Any:
    changed = copy.deepcopy(record)
    node = changed
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return changed


def test_two_identical_records_have_no_difference() -> None:
    assert replay.replay_differences(_record(), _record()) == []


@pytest.mark.parametrize(
    "path",
    [
        ("start", "coupling_record_sha256"),
        ("artifacts", "coupled_runs", 0, "sha256"),
    ],
)
def test_a_coupling_digest_is_compared_for_shape_only(path: tuple[Any, ...]) -> None:
    assert replay.replay_differences(_record(), _set(_record(), path, "f" * 64)) == []


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("start", "coupling_record_sha256"), None),
        (("candidates", 0, "solves", 0, "coupling_record_sha256"), "f" * 64),
        (("start", "coupling_record_sha256"), "F" * 64),
        (("artifacts", "coupled_runs", 0, "check_id"), "S1"),
        (("start", "objective"), math.nextafter(1.25, 2.0)),
        (("start", "objective"), 1),
        (("start", "wall_s"), 0.0),
    ],
)
def test_the_comparator_finds(path: tuple[Any, ...], value: Any) -> None:
    """A null against a digest, a malformed digest, another check id, one ulp, an int for a
    float, and an excluded timing that is not positive."""
    assert len(replay.replay_differences(_record(), _set(_record(), path, value))) == 1


def test_an_excluded_timing_is_not_compared() -> None:
    assert replay.replay_differences(_record(), _set(_record(), ("start", "wall_s"), 9.0)) == []


def test_the_excluded_paths_are_read_from_the_addenda() -> None:
    assert [p.pattern for p in replay.m05_excluded()] == [
        r"\.(start|candidates\[\d+\]\.solves\[\d+\])\.wall_s"
    ]
    (timing,) = replay.m02_coupling_excluded()
    assert timing.fullmatch(".iterations[0].units.reactor.attempts[0].execution.timing.wall_s")


def _persist(directory: Path, documents: dict[str, Any]) -> Path:
    directory.mkdir()
    for name, document in documents.items():
        (directory / f"{name}.json").write_bytes(canonical_json(document))
    return directory


def test_the_persisted_records_pass_integrity(tmp_path: Path) -> None:
    directory = _persist(tmp_path / "x.coupling", {"S0": COUPLING})
    assert replay.persisted_violations(_record(), directory) == []


@pytest.mark.parametrize(
    "documents",
    [
        {"S0": {**COUPLING, "coupling_block": {"tau_xi_rel": 2e-6}}},
        {"S0": COUPLING, "S1": COUPLING},
        {},
    ],
    ids=["tampered", "extra", "missing"],
)
def test_the_integrity_check_finds(tmp_path: Path, documents: dict[str, Any]) -> None:
    directory = _persist(tmp_path / "x.coupling", documents)
    assert replay.persisted_violations(_record(), directory) != []


def test_the_content_check_removes_m02s_excluded_timings() -> None:
    fresh = copy.deepcopy(COUPLING)
    fresh["iterations"][0]["units"]["reactor"]["attempts"][0]["execution"]["timing"] = {
        "wall_s": 0.5,
        "started": 99.0,
    }
    assert replay.content_differences(COUPLING, fresh) == []


def test_the_content_check_compares_every_other_float_bitwise() -> None:
    fresh = copy.deepcopy(COUPLING)
    fresh["iterations"][0]["w"][1] = math.nextafter(12.5, 13.0)
    assert len(replay.content_differences(COUPLING, fresh)) == 1
