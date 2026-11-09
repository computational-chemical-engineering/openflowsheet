"""R-1008 (`docs/reviews/REL040-s6-ruling.md` §8 WO-3, S6R-11 to S6R-15, as replaced by §11.4 WO-8):
`scripts/m01_idaes_retake_diff.py` on copies of the committed IDAES conformance record.

§8.0 (as amended by §11.4): no assertion depends on the host or the date at which the committed
record was taken. The old platform P0 is read from the record; every new platform and the new
`environment.python` are made-up literals that no host prints, asserted at import to differ from the
record's. The stale input hash of S6R-14 is set synthetically on the committed side.

A re-take passes iff every member under step 11's comparator is equal, except `environment.platform`
moving from `--old-platform` to the running `platform.platform()`, and an `inputs.<name>_sha256`
of a registered input that equals its tracked, unmodified file's SHA-256.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import platform
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "benchmarks" / "m01" / "idaes-conformance.json"
REFERENCE_VALUES = ROOT / "benchmarks" / "m01" / "reference_values.yaml"


def _script() -> ModuleType:
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "m01_idaes_retake_diff", ROOT / "scripts" / "m01_idaes_retake_diff.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RETAKE = _script()
COMMITTED: dict[str, Any] = json.loads(RECORD.read_bytes())
P0: str = COMMITTED["environment"]["platform"]
P1 = "Linux-0.0.0-s6r12-retake"
P_OTHER_RUNNING = "Linux-0.0.0-s6r13-running"
P_OTHER_OLD = "Linux-0.0.0-s6r13-old"
PYTHON_MOVED = "0.0.0-s6r15"
STALE_INPUT_SHA256 = "5" * 64
for _made_up in (P1, P_OTHER_RUNNING, P_OTHER_OLD):
    assert _made_up != P0, f"{_made_up!r} must differ from the committed platform"
assert PYTHON_MOVED != COMMITTED["environment"]["python"]


@pytest.fixture
def running_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "platform", lambda: P1)


def _retake() -> dict[str, Any]:
    return copy.deepcopy(COMMITTED)


def _on_p1() -> dict[str, Any]:
    retake = _retake()
    retake["environment"]["platform"] = P1
    return retake


def test_s6r11_a_byte_copy_passes_with_nothing_differing() -> None:
    passed, lines = RETAKE.retake_diff(COMMITTED, json.loads(RECORD.read_bytes()))
    assert passed, lines
    assert lines == ["IDAES-RETAKE PASS differing= platform=0 inputs=0 other=0"]


def test_s6r12_the_platform_pinned_on_both_sides_passes(running_p1: None) -> None:
    passed, lines = RETAKE.retake_diff(COMMITTED, _on_p1(), P0)
    assert passed, lines
    assert lines == ["IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0"]


@pytest.mark.parametrize(
    ("running", "old_platform", "problem"),
    [
        (P1, None, "(no --old-platform)"),
        (
            P_OTHER_RUNNING,
            "<committed>",
            f"re-take {P1!r} is not the running {P_OTHER_RUNNING!r}",
        ),
        (P1, P_OTHER_OLD, "is not --old-platform"),
    ],
)
def test_s6r13_the_platform_without_its_pins_fails(
    monkeypatch: pytest.MonkeyPatch, running: str, old_platform: str | None, problem: str
) -> None:
    monkeypatch.setattr(platform, "platform", lambda: running)
    pinned = P0 if old_platform == "<committed>" else old_platform
    passed, lines = RETAKE.retake_diff(COMMITTED, _on_p1(), pinned)
    assert not passed
    assert "platform=0 inputs=0 other=1" in lines[0]
    assert any(
        line.startswith("  other environment.platform: ") and problem in line for line in lines
    )


def test_s6r14_the_reference_values_hash_of_the_tree_file_passes() -> None:
    # The committed side carries a made-up stale hash, so the case does not depend on whether the
    # committed record predates the tree file (ruling §11.4, WO-8).
    actual = hashlib.sha256(REFERENCE_VALUES.read_bytes()).hexdigest()
    assert actual != STALE_INPUT_SHA256
    committed = _retake()
    committed["inputs"]["reference_values_yaml_sha256"] = STALE_INPUT_SHA256
    retake = _retake()
    retake["inputs"]["reference_values_yaml_sha256"] = actual
    passed, lines = RETAKE.retake_diff(committed, retake)
    assert passed, lines
    assert lines == [
        "IDAES-RETAKE PASS differing=inputs.reference_values_yaml_sha256 platform=0 inputs=1 "
        "other=0"
    ]


def test_s6r14_an_input_hash_that_is_not_its_file_fails() -> None:
    retake = _retake()
    retake["inputs"]["reference_values_yaml_sha256"] = "0" * 64
    passed, lines = RETAKE.retake_diff(COMMITTED, retake)
    assert not passed
    assert "inputs=0 other=1" in lines[0]
    assert any(
        line.startswith("  other inputs.reference_values_yaml_sha256: ")
        and "is not the SHA-256 of benchmarks/m01/reference_values.yaml" in line
        for line in lines
    )


def test_s6r14_an_unknown_input_hash_fails() -> None:
    retake = _retake()
    retake["inputs"]["unknown_sha256"] = "0" * 64
    passed, lines = RETAKE.retake_diff(COMMITTED, retake)
    assert not passed
    assert "  other inputs.unknown_sha256: not a registered input" in lines


def _first_float(document: Any, path: str = "") -> tuple[str, list[str]]:
    """The dotted member of the first float leaf reached through objects only, and its keys."""
    if isinstance(document, dict):
        for key, value in document.items():
            if isinstance(value, float):
                return f"{path}{key}", [key]
            if isinstance(value, dict):
                found = _first_float(value, f"{path}{key}.")
                if found[0]:
                    return found[0], [key, *found[1]]
    return "", []


def _nudge(document: dict[str, Any]) -> str:
    """Moves the first float of `phase_states` by one ulp; returns its member."""
    member, keys = _first_float(document["phase_states"], "phase_states.")
    assert member, "the record holds a float under phase_states"
    holder = document["phase_states"]
    for key in keys[:-1]:
        holder = holder[key]
    holder[keys[-1]] = math.nextafter(holder[keys[-1]], math.inf)
    return member


def _python(document: dict[str, Any]) -> str:
    document["environment"]["python"] = PYTHON_MOVED
    return "environment.python"


@pytest.mark.parametrize("change", [_nudge, _python])
def test_s6r15_a_moved_member_is_other(change: Any) -> None:
    retake = _retake()
    member = change(retake)
    passed, lines = RETAKE.retake_diff(COMMITTED, retake)
    assert not passed
    assert "other=1" in lines[0]
    assert any(line.startswith(f"  other {member}: ") for line in lines)


def test_s6r15_the_platform_and_a_number_moving_together_fail_on_the_number(
    running_p1: None,
) -> None:
    retake = _on_p1()
    member = _nudge(retake)
    passed, lines = RETAKE.retake_diff(COMMITTED, retake, P0)
    assert not passed
    assert "platform=1 inputs=0 other=1" in lines[0]
    assert any(line.startswith(f"  other {member}: ") for line in lines)
