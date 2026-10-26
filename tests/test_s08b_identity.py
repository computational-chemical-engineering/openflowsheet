"""S08b WO-1 — gate G1's rule (S08b design note §9 G1, R-794), as `scripts/s08b_identity.py`
applies it.

The gate itself runs the 52 registered configurations and the whole suite's decision log on the
merge base and on the branch; these tests pin that its verdict passes on exactly §9's outcome
(and, under `--no-change`, on no difference at all) and fails on every other, so that the gate
cannot report success by construction.
"""

from __future__ import annotations

import copy
import math
import sys
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import s08b_identity  # noqa: E402
import s08b_identity_recorder  # noqa: E402

MOVED = s08b_identity.MOVED
_EMPTY = "phase_wall(stall, )"


def _message(name: str) -> str:
    return f"active_set_cycling({name}.stage.1:TWO_PHASE; {_EMPTY})"


def _trees() -> tuple[dict[str, Any], dict[str, Any]]:
    """A merge base and a branch that differ exactly as §9 G1 expects."""
    names = sorted({name for name, _ in MOVED} | {f"X.{i}" for i in range(52 - 11)})
    texts: dict[str, dict[str, str]] = {name: {"result.message": ""} for name in names}
    for name, path in MOVED:
        texts[name][path] = _message(name)
        texts[name]["recovered_from.attempts[0].reason"] = "reason"
    base_a = {
        "digests": {name: f"d-{name}" for name in names},
        "stage_a": {"S02.P1": "s-P1"},
        "texts": texts,
    }
    branch_a = copy.deepcopy(base_a)
    for (name, path), changes in MOVED.items():
        branch_a["texts"][name][path] = _message(name).replace(
            _EMPTY, f"phase_wall(stall, {changes})"
        )
    wall = "phase_update(phase_wall(patience, ))"
    base_b = {
        "records": {
            "t::a#0": ["h0", "", ""],
            "t::a#1": ["h1", wall, "phase_wall(patience, )"],
            "t::b#0": ["h2", "phase_update(closure_projection(U-FLASH))", "closure_projection"],
        },
        "exit": [0, 0],
    }
    branch_b = copy.deepcopy(base_b)
    branch_b["records"]["t::a#1"] = [
        "h1",
        "phase_update(phase_wall(patience, C.stage.1:LIQUID->TWO_PHASE, C.stage.3:VAPOR->LIQUID))",
        "phase_wall(patience, C.stage.1:LIQUID->TWO_PHASE, C.stage.3:VAPOR->LIQUID)",
    ]
    return {"a": base_a, "b": base_b}, {"a": branch_a, "b": branch_b}


def test_g1_the_verdict_passes_on_the_registered_differences_only() -> None:
    passed, line = s08b_identity.verdict(*_trees())
    assert passed, line
    assert line == "S08B-IDENTITY PASS a=52 a_texts=11 b_keys=3 b_moved=1 b_only=0/0"


def test_g1_no_change_passes_on_equal_trees_and_fails_on_the_registered_move() -> None:
    base, _ = _trees()
    passed, line = s08b_identity.verdict(base, copy.deepcopy(base), no_change=True)
    assert passed and line == "S08B-IDENTITY PASS a=52 a_texts=0 b_keys=3 b_moved=0 b_only=0/0"
    passed, line = s08b_identity.verdict(*_trees(), no_change=True)
    assert not passed and line.startswith("S08B-IDENTITY FAIL ")


def _a_twelfth_moved_text(base: Any, branch: Any) -> None:
    base["a"]["texts"]["X.3"]["recovered_from.message"] = _message("X")
    branch["a"]["texts"]["X.3"]["recovered_from.message"] = _message("X").replace(
        _EMPTY, "phase_wall(stall, X.stage.1:VAPOR->TWO_PHASE)"
    )


def _a_wrong_list(base: Any, branch: Any) -> None:
    key = ("S02.M1", "recovered_from.message")
    branch["a"]["texts"]["S02.M1"][key[1]] = _message("S02.M1").replace(
        _EMPTY, "phase_wall(stall, S02.stage.6:VAPOR->TWO_PHASE)"
    )


def _a_registered_text_unmoved(base: Any, branch: Any) -> None:
    branch["a"]["texts"]["S03.RC7"]["recovered_from.message"] = _message("S03.RC7")


def _a_moved_reason(base: Any, branch: Any) -> None:
    branch["a"]["texts"]["S02.M1"]["recovered_from.attempts[0].reason"] = "other"


def _a_moved_digest(base: Any, branch: Any) -> None:
    branch["a"]["digests"]["X.0"] = "moved"


def _a_moved_stage_a(base: Any, branch: Any) -> None:
    branch["a"]["stage_a"]["S02.P1"] = "moved"


def _a_lost_stage_a(base: Any, branch: Any) -> None:
    del branch["a"]["stage_a"]["S02.P1"]


def _a_51_configurations(base: Any, branch: Any) -> None:
    for tree in (base, branch):
        del tree["a"]["digests"]["X.0"]
        del tree["a"]["texts"]["X.0"]


def _b_moved_alpha(base: Any, branch: Any) -> None:
    """A moved candidate α (or any structural field) changes the record's structural hash."""
    branch["b"]["records"]["t::a#1"][0] = s08b_identity_recorder._hash("alpha moved")


def _b_non_stage_list(base: Any, branch: Any) -> None:
    branch["b"]["records"]["t::a#1"] = [
        "h1",
        "phase_update(phase_wall(patience, U-HEAT:LIQUID->VAPOR))",
        "phase_wall(patience, U-HEAT:LIQUID->VAPOR)",
    ]


def _b_item_entry_in_list(base: Any, branch: Any) -> None:
    wall = "phase_wall(patience, C.stage.1:LIQUID->TWO_PHASE, U-PUMP.outlet:ZERO_FLOW->LIQUID)"
    branch["b"]["records"]["t::a#1"] = ["h1", f"phase_update({wall})", wall]


def _b_other_text(base: Any, branch: Any) -> None:
    branch["b"]["records"]["t::b#0"][1] = "phase_update(closure_projection(U-OTHER))"


def _b_shard_failed(base: Any, branch: Any) -> None:
    branch["b"]["exit"][1] = 1


def _b_nothing_shared(base: Any, branch: Any) -> None:
    branch["b"]["records"] = {}


@pytest.mark.parametrize(
    "mutate",
    [
        _a_twelfth_moved_text,
        _a_wrong_list,
        _a_registered_text_unmoved,
        _a_moved_reason,
        _a_moved_digest,
        _a_moved_stage_a,
        _a_lost_stage_a,
        _a_51_configurations,
        _b_moved_alpha,
        _b_non_stage_list,
        _b_item_entry_in_list,
        _b_other_text,
        _b_shard_failed,
        _b_nothing_shared,
    ],
)
def test_g1_the_verdict_fails_on_any_other_outcome(mutate: Any) -> None:
    base, branch = _trees()
    mutate(base, branch)
    passed, line = s08b_identity.verdict(base, branch)
    assert not passed and line.startswith("S08B-IDENTITY FAIL "), line


def test_g1_keys_in_one_tree_only_are_reported_not_judged() -> None:
    base, branch = _trees()
    branch["b"]["records"]["t::new#0"] = ["h9", "", ""]
    passed, line = s08b_identity.verdict(base, branch)
    assert passed and line.endswith("b_only=0/1")


def test_g1_the_stage_list_move() -> None:
    move = s08b_identity.stage_list_move
    old = "active_set_cycling(S.stage.1:TWO_PHASE; phase_wall(stall, ))"
    assert move(old, old.replace(", ))", ", S.stage.1:LIQUID->TWO_PHASE))"))
    assert not move(old, old)  # nothing filled in
    assert not move(old, old.replace(", ))", ", S.stage.1:LIQUID->LIQUID))"))  # no change
    assert not move("phase_wall(stall, X)", "phase_wall(stall, S.stage.1:LIQUID->VAPOR)")


def test_g1_the_opening_hash_reads_every_bit() -> None:
    """§9 G1: a `(state, regimes)` opening by sorted ids and `float.hex`; a vector likewise."""
    digest = s08b_identity_recorder.opening_sha256
    state = {"b": 1.0, "a": 0.1}
    assert digest((state, {"U": "LIQUID"})) == digest(({"a": 0.1, "b": 1.0}, {"U": "LIQUID"}))
    assert digest((state, {"U": "LIQUID"})) != digest((state, {"U": "VAPOR"}))
    nudged = {"b": 1.0, "a": math.nextafter(0.1, 1.0)}
    assert digest((state, {"U": "LIQUID"})) != digest((nudged, {"U": "LIQUID"}))
    assert digest([0.1, 1.0]) != digest([0.1, 1.0000000000000002])


def test_g1_the_gate_covers_52_configurations_and_eleven_texts() -> None:
    """§9 G1 / §6.1: S08's 52 configurations; eleven registered texts on eleven configurations."""
    import s08_identity
    from test_s01_cascade_wo1 import CASES

    assert len(s08_identity.column_configurations()) + len(CASES) == 52
    assert s08b_identity.CONFIGURATIONS == 52
    assert len(MOVED) == 11 and len({name for name, _ in MOVED}) == 11
    assert set(MOVED) <= {
        (name, path)
        for name in s08_identity.column_configurations()
        for path in ("recovered_from.message", "reentry.stage_a.recovered_from.message")
    }
