"""S08 WO-4 — gate G1's rule (S08 design note §9 G1, §7 A13), as `scripts/s08_identity.py`
applies it.

The gate itself runs the 52 registered configurations on the merge base and on the branch (the
evidence manifest runs it); these tests pin that its verdict passes on exactly §9's outcome and
fails on every other, so that the gate cannot report success by construction.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import s08_identity  # noqa: E402

NAMES = [f"S02.{case}" for case in ("M1", "M2", "M3", "M4", "P1")] + [
    f"X.{index}" for index in range(47)
]


def _trees(**changes: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """A merge base and a branch that differ exactly as §9 G1 expects, then `changes`."""
    base = {"digests": {name: f"old-{name}" for name in NAMES}, "stage_a": {}}
    branch = {
        "digests": {**base["digests"], "S02.P1": "new-P1"},
        "stage_a": {"S02.P1": "old-S02.P1"},
    }
    for key, value in changes.items():
        tree, field, name = key.split("__")
        target = {"base": base, "branch": branch}[tree][field]
        if value is None:
            del target[name.replace("_", ".", 1)]
        else:
            target[name.replace("_", ".", 1)] = value
    return base, branch


def test_a13_the_verdict_passes_on_the_registered_change_only() -> None:
    passed, line = s08_identity.verdict(*_trees())
    assert passed and line == s08_identity.PASS_LINE


@pytest.mark.parametrize(
    "changes",
    [
        {"branch__digests__S02_M1": "moved"},  # another configuration changed
        {"branch__digests__S02_P1": "old-S02.P1"},  # P1 unchanged: Stage B did nothing
        {"branch__stage_a__S02_P1": "other"},  # P1's Stage A is not the merge base's answer
        {"branch__stage_a__S02_P1": None},  # P1 has no `reentry`
        {"branch__stage_a__X_3": "other"},  # another Stage A differs from its merge base
        {"branch__digests__X_46": None, "base__digests__X_46": None},  # 51 configurations
        {"branch__digests__X_46": None},  # the trees disagree on the configurations
        {"base__stage_a__S02_P1": "old-S02.P1"},  # the merge base already has S08's records
    ],
)
def test_a13_the_verdict_fails_on_any_other_outcome(changes: dict[str, Any]) -> None:
    passed, line = s08_identity.verdict(*_trees(**changes))
    assert not passed and line.startswith("S08-IDENTITY FAIL ")


def test_a13_the_gate_covers_52_configurations() -> None:
    """§9 G1: the 47 column configurations of §3 F3 plus S01 C1–C5."""
    from test_s01_cascade_wo1 import CASES

    assert len(s08_identity.column_configurations()) == 47
    assert len(CASES) == 5 and s08_identity.CONFIGURATIONS == 52
