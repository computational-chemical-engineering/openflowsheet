"""F0: the corpus identity gate (`scripts/corpus_identity.py`) and its four exit mutations.

Target architecture §3 F0, exit N2. Every mutation is test-only (a monkeypatch or a copy in
`tmp_path`); no committed fixture or module is edited.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402

RUN = ("g8", "SYN-001-nominal")
KEY = "/".join(RUN)


@pytest.fixture(scope="module")
def registered() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def platform() -> str:
    return gate.reference_class()


@pytest.fixture(scope="module")
def full(registered: dict[str, Any], platform: str) -> tuple[dict[str, Any], list[str]]:
    return gate.compare(registered, gate.measure_all(), platform)


def judged(registered: dict[str, Any], measured: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # M4 is judged here whatever the host: the mutations below must move it bitwise, and a
    # state hash that moved on the reference platform moved everywhere it is compared.
    results, _ = gate.compare(registered, measured, registered["reference_platform"], subset=True)
    return results


def test_every_implemented_measure_passes(full: tuple[dict[str, Any], list[str]]) -> None:
    results, log = full
    implemented = {m: r for m, r in results.items() if m not in gate.NOT_IMPLEMENTED}
    assert all(r["status"] in ("PASS", "NOT JUDGED") for r in implemented.values()), log
    assert results["M1"]["n"] == 50 and results["M2"]["n"] == 52 and results["M9"]["n"] == 8


@pytest.mark.xfail(strict=True, reason="M7 and M8 are not implemented (docs/F0_DECISIONS.md)")
def test_the_gate_passes(full: tuple[dict[str, Any], list[str]]) -> None:
    passed, line = gate.summary(full[0])
    assert passed, line


def test_a_not_implemented_measure_fails_the_gate() -> None:
    passed, line = gate.summary(
        {"M1": {"status": "PASS", "n": 1}, "M7": {"status": "NOT IMPLEMENTED"}}
    )
    assert not passed and "M7 NOT IMPLEMENTED" in line


def _mappings(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _mappings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _mappings(value)


def _one_ulp_split_fraction(document: dict[str, Any]) -> float:
    """SYN-001's split fraction r, one ulp up, in the instance and in the fixed specification
    that pins it (SPEC-splitter-r); moving one without the other is a specification conflict."""
    pinned = [
        m
        for m in _mappings(document)
        if isinstance(m.get("target"), dict)
        and m["target"].get("object_id") == "splitter"
        and m["target"].get("path") == "parameters.split_fraction"
    ]
    splitter = next(m for m in _mappings(document) if m.get("id") == "splitter")
    parameter = splitter["parameters"]["split_fraction"]
    assert len(pinned) == 1 and pinned[0]["value"] == parameter["value"] == 0.5
    moved = math.nextafter(parameter["value"], math.inf)
    parameter["value"] = pinned[0]["value"] = moved
    return moved


def test_exit_2_one_ulp_in_a_registered_parameter_moves_m2_m3_m4(
    registered: dict[str, Any],
) -> None:
    from t07_corpus import CORPUS

    document = CORPUS[RUN[1]]()
    assert _one_ulp_split_fraction(document) == 0.5 + 2.0**-53
    measured = gate.runs([RUN], {RUN[1]: document})[KEY]
    results = judged(registered, {m: {KEY: measured[m]} for m in ("M2", "M3", "M4")})
    assert {m: r["status"] for m, r in results.items()} == {
        "M2": "FAIL",
        "M3": "FAIL",
        "M4": "FAIL",
    }
    expected = registered["measures"]["M2"][KEY]
    assert measured["M2"]["model_version"] == expected["model_version"]
    assert measured["M2"]["constants_sha256"] != expected["constants_sha256"]


def test_exit_3_one_flipped_check_result_fails_m5(
    registered: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    read = gate.artifacts

    def flipped(directory: Path) -> tuple[Any, dict[str, Any]]:
        manifest, documents = read(directory)
        check = documents["solution-certificate.json"]["checks"][0]
        check["result"] = "fail" if check["result"] == "pass" else "pass"
        return manifest, documents

    unmutated = gate.runs([RUN])[KEY]
    assert judged(registered, {"M5": {KEY: unmutated["M5"]}})["M5"]["status"] == "PASS"
    monkeypatch.setattr(gate, "artifacts", flipped)
    measured = gate.runs([RUN])[KEY]
    assert judged(registered, {"M5": {KEY: measured["M5"]}})["M5"]["status"] == "FAIL"


def test_exit_4_one_byte_in_a_frozen_module_fails_m9_by_name(
    registered: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(ROOT / "src", tmp_path / "src", symlinks=True)
    name = sorted(registered["measures"]["M9"])[0]
    target = tmp_path / name
    data = bytearray(target.read_bytes())
    data[-1] ^= 0x01
    target.write_bytes(bytes(data))
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    results, log = gate.compare(registered, {"M9": gate.m9()}, "", subset=True)
    assert results["M9"]["status"] == "FAIL" and results["M9"]["wrong"] == [name]
    assert any(line.startswith(f"M9: {name}:") for line in log)


def test_m9_enumerates_from_the_hash_sites_not_by_hand() -> None:
    modules = gate.identity_bearing_modules()
    assert "src/openflowsheet/thermo/wilson_ig.py" in modules
    assert "src/openflowsheet/thermo/_coolprop_heos_fluids.py" in modules
