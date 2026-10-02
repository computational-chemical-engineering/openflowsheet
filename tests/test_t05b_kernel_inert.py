"""T05b B02: the PH kernel is inert on T05's registered calls (T05b spec §5.4, §14 B02).

The committed baseline `tests/fixtures/t05b/ph_state_baseline.json` was emitted by
`scripts/t05b_ph_baseline.py` before T05b changed the kernel (W0.1). A live run of the same
generator must reproduce it byte for byte: every registered `ph_state` call's inputs and answer
(status, code, message, route, temperature, split, evaluations, residual) and every registered
unit case's answer, as `float.hex()` strings, so a changed last bit or a flipped zero sign fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import t05b_ph_baseline as baseline  # noqa: E402


@pytest.fixture(scope="module")
def live() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(baseline.render(baseline.collect()))
    return document


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(baseline.FIXTURE.read_text())
    return document


def test_the_baseline_is_what_the_generator_emits_today(live: dict[str, Any]) -> None:
    assert baseline.render(live) == baseline.FIXTURE.read_text()


@pytest.mark.parametrize("group", ["unit_cases", "kernel_targets", "coupled_cases"])
def test_every_registered_call_is_bitwise_the_baseline(
    group: str, live: dict[str, Any], committed: dict[str, Any]
) -> None:
    """Per case, so a failure names the call that moved."""
    assert sorted(live[group]) == sorted(committed[group])
    for case_id, recorded in committed[group].items():
        assert live[group][case_id] == recorded, case_id


def test_the_baseline_covers_the_registered_calls(committed: dict[str, Any]) -> None:
    """Spec B02's list: PHF-1…7 and PHF-F1…F4, the flowing valve cases, the duty-mode reactor
    cases, and C1–C3's traversals; each with at least the kernel calls T05 registers."""
    units = committed["unit_cases"]
    routes = {case: [c["answer"]["route"] for c in units[case]["calls"]] for case in units}
    for case in ("PHF-1", "PHF-2", "PHF-3", "PHF-4", "PHF-5", "PHF-7"):
        assert routes[case] == ["bracket"], case
    assert routes["PHF-6"] == ["saturation"]
    for case in ("VLV-1", "VLV-2", "VLV-3", "VLV-4", "VLV-5", "RX-3", "RX-5"):
        assert routes[case] == ["bracket"], case
    for case in ("PHF-F1", "PHF-F2", "RX-F5"):
        assert [c["answer"]["status"] for c in units[case]["calls"]] == ["out_of_domain"], case
    coupled = committed["coupled_cases"]
    assert [len(coupled[case]["calls"]) for case in sorted(coupled)] == [2, 0, 2, 1]
    assert len(committed["kernel_targets"]) == 8
