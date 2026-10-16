"""G10's comparator and referent check in test support (`tests/support/m05_replay.py`; design note
§9.3, §19.1, §19.4; register R-384, R-385), on hand-built records: the coupling digests compared
for shape and their check ids exactly, every other float bitwise, `wall_s` excluded and positive;
the persisted coupling records' integrity (one file per coupled run, its sha256 the recorded
digest) and content (M02's `excluded` paths removed, floats by `float.hex`); §8.3's store
bijection (G7) of a store's attempts against a ledger and coupling records, and what it finds.

Default gate: no Pyomo, nothing runs.
"""

from __future__ import annotations

import copy
import json
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
        r"\.(start|candidates\[\d+\]\.solves\[\d+\])\.wall_s",
        r"\.provenance\.wall_s",
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


# -- §8.3's store bijection (G7) ---------------------------------------------------------------

KEY_A, KEY_B = "a" * 64, "b" * 64


def _attempted(key: str, number: int) -> dict[str, Any]:
    return {"experiment_key": key, "attempt": number}


def _bijection_case() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """A store with A's attempt 1 from a coupled solve, A's attempt 2 and B's attempts 1-2 from
    the ledger (one of them a store hit with no executions)."""
    store = [_attempted(KEY_A, 1), _attempted(KEY_A, 2), _attempted(KEY_B, 1), _attempted(KEY_B, 2)]
    coupling = {"iterations": [{"units": {"reactor": {"attempts": [_attempted(KEY_A, 1)]}}}]}
    requests = [
        {"seq": 0, "experiment_key": KEY_A, "executions": 1},
        {"seq": 1, "experiment_key": KEY_B, "executions": 2},
        {"seq": 2, "experiment_key": KEY_B, "executions": 0},
    ]
    return store, [{"holder": "link:reactor", "requests": requests}], {"S0": coupling}


def test_the_store_bijection_holds() -> None:
    assert replay.store_bijection_violations(*_bijection_case()) == []


def _unattributed(store: list[Any], ledger: list[Any], couplings: dict[str, Any]) -> None:
    store.append(_attempted(KEY_B, 3))


def _claimed_twice(store: list[Any], ledger: list[Any], couplings: dict[str, Any]) -> None:
    couplings["B1"] = copy.deepcopy(couplings["S0"])


def _not_stored(store: list[Any], ledger: list[Any], couplings: dict[str, Any]) -> None:
    store.remove(_attempted(KEY_A, 1))
    ledger[0]["requests"][0]["executions"] = 0


def _ledger_beyond_store(store: list[Any], ledger: list[Any], couplings: dict[str, Any]) -> None:
    ledger[0]["requests"][2]["executions"] = 1


def _without_key(store: list[Any], ledger: list[Any], couplings: dict[str, Any]) -> None:
    ledger[0]["requests"][0]["experiment_key"] = None


@pytest.mark.parametrize(
    "mutate",
    [_unattributed, _claimed_twice, _not_stored, _ledger_beyond_store, _without_key],
    ids=["unattributed", "claimed_twice", "not_stored", "ledger_beyond_store", "without_key"],
)
def test_the_store_bijection_finds(mutate: Any) -> None:
    store, ledger, couplings = _bijection_case()
    mutate(store, ledger, couplings)
    assert replay.store_bijection_violations(store, ledger, couplings) != []


# -- REAL: the replay from the record (WO-9, F-20, build log S68) ---------------------------------

RECORDS = REPO_ROOT / "benchmarks" / "m05" / "records"
LOOP_R = RECORDS / "trust-region-study-loop-r"


def _committed(suffix: str) -> Any:
    return json.loads(LOOP_R.with_suffix(suffix).read_text(encoding="utf-8"))


def _served_record(record: dict[str, Any]) -> dict[str, Any]:
    """`record` as a replay from the record writes it: every cold request a store hit."""
    fresh = copy.deepcopy(record)
    for run in fresh["runs"]:
        run["cold"] = run["ledger"]["cold_parent"] = 0
        for summary in run["ledger"]["summary"].values():
            for call in ("value", "jacobian"):
                summary[f"{call}_store_hit"] += summary[f"{call}_cold"]
                summary[f"{call}_cold"] = 0
    accounting = fresh["accounting"]
    accounting["totals"]["trf_cold"] = accounting["totals"]["parent_executions"] = 0
    accounting["budgets"]["cold_used"] = 0
    for solve in [fresh["start"], *(s for c in fresh["candidates"] for s in c["solves"])]:
        solve["experiments"]["store_hits"] += solve["experiments"]["executions"]
        solve["experiments"]["executions"] = 0
    return fresh


def _served_ledger(ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fresh = copy.deepcopy(ledger)
    for block in fresh:
        for entry in block["requests"]:
            if entry["served"] == "cold":
                entry.update(served="store_hit", executions=0)
    return fresh


def _served_coupling(record: dict[str, Any]) -> dict[str, Any]:
    fresh = copy.deepcopy(record)
    for item in fresh["iterations"]:
        for entry in item["units"].values():
            if entry["request"] is not None:
                entry.update(cache_hit=True, attempts=[])
    return fresh


def test_a_replay_from_the_record_differs_only_by_design() -> None:
    record = _committed(".json")
    record["provenance"] = {"run_commit": "a" * 40, "tree_clean": True, "wall_s": 9.0}
    assert record["accounting"]["totals"]["trf_cold"] > 0  # the shift is not vacuous
    assert replay.real_replay_differences(record, _served_record(record)) == []


def test_the_real_comparator_finds_a_moved_decision_and_an_execution() -> None:
    record = _committed(".json")
    moved = _served_record(record)
    (name,) = moved["best"]["decisions"]
    moved["best"]["decisions"][name] = math.nextafter(moved["best"]["decisions"][name], 1e3)
    assert len(replay.real_replay_differences(record, moved)) == 1
    executed = _served_record(record)
    executed["accounting"]["totals"]["trf_cold"] = 3
    assert replay.real_replay_differences(record, executed) == ["replay executed: trf_cold = 3"]
    lost = _served_record(record)
    summary = next(iter(lost["runs"][0]["ledger"]["summary"].values()))
    summary["value_store_hit"] -= 1
    assert len(replay.real_replay_differences(record, lost)) == 1


def test_the_served_ledger_maps_cold_to_store_hits_only() -> None:
    ledger = _committed(".ledger.json")
    assert any(e["served"] == "cold" for b in ledger for e in b["requests"])
    assert replay.served_ledger_differences(ledger, _served_ledger(ledger)) == []
    kept = _served_ledger(ledger)
    cold = next(
        (b, i)
        for b, block in enumerate(ledger)
        for i, e in enumerate(block["requests"])
        if e["served"] == "cold"
    )
    kept[cold[0]]["requests"][cold[1]]["served"] = "cold"
    assert len(replay.served_ledger_differences(ledger, kept)) == 1
    keyed = _served_ledger(ledger)
    keyed[cold[0]]["requests"][cold[1]]["experiment_key"] = "f" * 64
    assert len(replay.served_ledger_differences(ledger, keyed)) == 1


def test_a_served_coupling_record_matches_and_a_change_is_found() -> None:
    (path, *_) = sorted(LOOP_R.with_suffix(".coupling").glob("*.json"))
    record = json.loads(path.read_text(encoding="utf-8"))
    assert replay.served_coupling_differences(record, _served_coupling(record)) == []
    executed = _served_coupling(record)
    first = next(e for e in executed["iterations"][0]["units"].values() if e["request"])
    first["cache_hit"] = False
    assert len(replay.served_coupling_differences(record, executed)) == 1
    moved = _served_coupling(record)
    moved["iterations"][-1]["w"][0] *= 1.5
    assert replay.served_coupling_differences(record, moved)
